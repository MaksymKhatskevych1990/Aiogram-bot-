import aiohttp
from datetime import datetime, timezone
from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input

async def check_ethereum_transaction(tx_hash: str, target_address: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            url = ETHERSCAN_API_KEY
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": ETHERSCANAPI_KEY
            }
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}
                data = await response.json()
                tx_data = data.get("result")
                block_number = tx_data.get("blockNumber")
                logger.info("Получен data ------ ETH: %s", data)
                if not tx_data:
                    return {"success": False, "error": "Транзакция не найдена"}
                if tx_data.get("to", "").lower() != "0xdac17f958d2ee523a2206206994597c13d831ec7":
                    return {"success": False, "error": "Это не транзакция USDT"}
                decoded = decode_erc20_input(tx_data["input"])
                logger.info("Получен decoded ------ ETH: %s", decoded)
                if not decoded:
                    return {"success": False, "error": "Невозможно декодировать входные данные"}
                logger.info("Получен decoded ------ ETH: %s", decoded["to"].lower())
                if decoded["to"].lower() != target_address.lower():
                    return {"success": False, "error": "Токены отправлены на другой адрес"}
                params_latest = {
                    "module": "proxy",
                    "action": "eth_blockNumber",
                    "apikey": ETHERSCAN_API_KEY
                }
                async with session.get(ETHERSCAN_API_KEY, params=params_latest) as resp_latest:
                    latest_block_data = await resp_latest.json()
                    latest_block_hex = latest_block_data.get("result")
                    if not latest_block_hex:
                        return {"success": False, "error": "Не удалось получить номер последнего блока"}
                    latest_block = int(latest_block_hex, 16)
                tx_block = int(block_number, 16)
                confirmations = latest_block - tx_block + 1
                if confirmations < ERC20_CONFIRMATIONS:
                    return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}"}
                params_block = {
                    "module": "proxy",
                    "action": "eth_getBlockByNumber",
                    "tag": block_number,
                    "boolean": "true",
                    "apikey": ETHERSCAN_API_KEY
                }
                async with session.get(ETHERSCAN_API_KEY, params=params_block) as resp_block:
                    block_response = await resp_block.json()
                    block_data = block_response.get("result")
                    timestamp = block_data.get("timestamp")
                    ts_int = int(timestamp, 16)
                    dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
                return {
                    "success": True,
                    "status": "confirmed",
                    "amount_raw": decoded["amount"],
                    "amount": decoded["amount"] / 10**6,
                    "from": tx_data.get("from", ""),
                    "to": decoded["to"],
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "confirmations": confirmations
                }
    except Exception as e:
        return {"success": False, "error": f"Ошибка: {str(e)}"} 