import aiohttp
import asyncio
from datetime import datetime, timezone
from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input



async def get_confirmations_by_block(session, block_number_hex: str) -> tuple[int, str | None]:

    if not block_number_hex or not isinstance(block_number_hex, str) or not block_number_hex.startswith("0x"):
        return 0, "Некорректный blockNumber (None или не hex)"
    
    url = "https://api.etherscan.io/api"
    params_latest = {
        "module": "proxy",
        "action": "eth_blockNumber",
        "apikey": ETHERSCAN_API_KEY
    }
    async with session.get(url, params=params_latest) as resp_latest:
        latest_block_data = await resp_latest.json()
        latest_block_hex = latest_block_data.get("result")
        if not latest_block_hex:
            return 0, "Не удалось получить номер последнего блока"
        latest_block = int(latest_block_hex, 16)

    tx_block = int(block_number_hex, 16)
    confirmations = latest_block - tx_block
    logger.info(f"[BEAT] Количество блоков {confirmations} ----- {latest_block} ---- {tx_block}")
    return confirmations, None


async def check_confirmation_for_pending(tx_hash, block_number_hex):
    async with aiohttp.ClientSession() as session:
        url = "https://api.etherscan.io/api"
        params = {
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": ETHERSCAN_API_KEY
        }

        if not block_number_hex:
            logger.info(f"[BEAT] check_confirmation_for_pending блоков {block_number_hex} ")
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}

                data = await response.json()
                tx_data = data.get("result")

                if not tx_data.get("blockNumber"):
                    return {"success": False, "error": "Транзакция еще не включена в блок"}

                block_number_hex = tx_data.get("blockNumber")

            await asyncio.sleep(0.6)

        confirmations, error = await get_confirmations_by_block(session, block_number_hex)
        if error:
            return {"success": False, "error": error}

        if confirmations >= ERC20_CONFIRMATIONS:
            return {"success": True, "confirmations": confirmations, "blockNumber": block_number_hex}
        return {
            "success": False,
            "confirmations": confirmations,
            "error": f"Недостаточно подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}",
            "blockNumber": block_number_hex
        }


async def check_ethereum_transaction(tx_hash: str, target_address: str) -> dict:
    try:
        url = "https://api.etherscan.io/api"

        async with aiohttp.ClientSession() as session:
            # Получаем данные транзакции
            result_transaction = {
                    "success": True
                }
            
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": ETHERSCAN_API_KEY
            }
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    result_transaction.update({"success": False, "error": f"Ошибка API: {response.status}"})
                    return result_transaction
                
                data = await response.json()
                tx_data = data.get("result")

                if not tx_data:
                    result_transaction.update({"success": False, "error": "Транзакция не найдена"})
                    return result_transaction

                if not tx_data.get("blockNumber"):
                    result_transaction.update({"success": False, "error": "Транзакция еще не включена в блок"})
                    return result_transaction


                # Проверяем, что транзакция направлена в контракт USDT
                if tx_data.get("to", "").lower() != "0xdac17f958d2ee523a2206206994597c13d831ec7":
                    result_transaction.update({"success": False, "error": "Это не транзакция USDT"})
                    return result_transaction

                # Декодируем входные данные для проверки адреса назначения и суммы
                decoded = decode_erc20_input(tx_data["input"])
                if not decoded:
                    result_transaction.update({"success": False, "error": "Невозможно декодировать данные транзакции"})
                    return result_transaction
                if decoded["to"].lower() != target_address.lower():
                    to_address = decoded["to"].lower()
                    logger.info("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ to_address: %s", to_address)
                    result_transaction.update({"success": False, "error": "Токены отправлены на другой адрес"})
                    return result_transaction

            await asyncio.sleep(0.6)  # чтобы не превысить лимит 2 запроса/сек


            logger.info(f"[ethereum] blockNumber {type(tx_data.get("blockNumber"))}  -- {tx_data.get("blockNumber")}")
            block_number_hex = tx_data.get("blockNumber")

            confirmations, error = await get_confirmations_by_block(session, block_number_hex)
            logger.info("+++++++++ETH latest_block: %s", confirmations < ERC20_CONFIRMATIONS)
            if confirmations < ERC20_CONFIRMATIONS:
                result_transaction.update({"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}"})

            await asyncio.sleep(1) 
            # Получаем данные блока для timestamp
            params_block = {
                "module": "proxy",
                "action": "eth_getBlockByNumber",
                "tag": tx_data.get("blockNumber"),
                "boolean": "true",
                "apikey": ETHERSCAN_API_KEY
            }
            logger.info(f"[ethereum] --------------------------------------------------------------------- {params_block}")
            async with session.get(url, params=params_block) as resp_block:
                block_response = await resp_block.json()
                
                block_data = block_response.get("result")
                # logger.info("ETH block_data: %s", block_data)
                timestamp_hex = block_data.get("timestamp")
                logger.info(f"[ethereum] timestamp_hex {type(timestamp_hex)}  -- {timestamp_hex}")
                if not isinstance(block_data, dict) or not isinstance(timestamp_hex, str) or "timestamp" not in block_data:
                    result_transaction.update({"success": False, "error": "Не удалось получить timestamp блока"})
                    return result_transaction
                
                ts_int = int(block_data["timestamp"], 16)
                dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)

            result_transaction.update({
                "status": "confirmed" if result_transaction["success"]==True else "pending",
                "amount_raw": decoded["amount"],
                "amount": decoded["amount"] / 10**6,
                "from": tx_data.get("from", ""),
                "to": decoded["to"],
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "confirmations": confirmations,
                "blockNumber": tx_data.get("blockNumber")
            })
            logger.info("E------------------------------------------------TH result_transaction: %s", result_transaction)
            return result_transaction

    except Exception as e:
        logger.error("Ошибка в check_ethereum_transaction: %s", str(e))
        return {"success": False, "error": f"Ошибка: {str(e)}"}
