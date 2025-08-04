import aiohttp
import asyncio
from datetime import datetime, timezone
from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input

async def fetch_transaction(session, tx_hash: str) -> dict:
    """Получает данные транзакции по хэшу"""
    params = {
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": ETHERSCAN_API_KEY
    }
    async with session.get("https://api.etherscan.io/api", params=params) as resp:
        if resp.status != 200:
            return {"success": False, "error": "Ошибка API"}

        data = await resp.json()
        tx_data = data.get("result")
        if not tx_data:
            return {"success": False, "status": "pending", "error": "Транзакция не найдена"}

        return {"success": True, "data": tx_data}
    

async def check_in_block(tx_data, tx_hash: str) -> dict:
    
    if not tx_data:
        return {"success": False, "status": "pending", "error": "Транзакция не найдена"}
    
    block_number = tx_data.get("blockNumber")
    if not block_number:
        return {"success": False, "status": "pending", "error": "Транзакция не в блоке"}
    
    return {"success": True, "status": "confirmed"}


async def check_is_erc20(tx_data, tx_hash: str) -> dict:
    """Проверяет, что это транзакция USDT (ERC-20)"""
    
    # Проверяем, что получатель — контракт USDT
    if tx_data.get("to", "").lower() != "0xdac17f958d2ee523a2206206994597c13d831ec7":
        return {"success": False, "status": "invalid_token", "error": "Токен не соответствует ожидаемому (USDT)"}
    
    return {"success": True}


async def check_recipient(tx_data, target_address: str) -> dict:
    """Проверяет, что токены отправлены на нужный адрес"""

        
    decoded = decode_erc20_input(tx_data["input"])
    logger.info(f"[ethereum] --decoded-- {decoded} ")
    if not decoded:
        return {"success": False, "error": "Не удалось декодировать данные"}
    logger.info(f"[ethereum] --decoded-- {decoded['to'].lower()} ")
    if decoded["to"].lower() != target_address.lower():
        return {"success": False, "status": "invalid_recipient", "error": "Пользователь отправил на чужой/неправильный адрес", "amount": decoded["amount"]}
    
    return {"success": True, "amount": decoded["amount"]}


async def check_confirmations(session, block_number_hex: str) -> dict:
    """Проверяет количество подтверждений блока"""
    if not block_number_hex:
        return {"success": False, "status": "pending", "error": "Нет номера блока"}
    
    # Получаем текущий блок
    params_latest = {
        "module": "proxy",
        "action": "eth_blockNumber",
        "apikey": ETHERSCAN_API_KEY
    }
    async with session.get("https://api.etherscan.io/api", params=params_latest) as resp:
        latest_block_data = await resp.json()
        latest_block_hex = latest_block_data.get("result")
        logger.info(f"[ethereum] --latest_block_hex-- {latest_block_hex} ")
        if not latest_block_hex:
            return {"success": False, "status": "pending", "error": "Не удалось получить последний блок"}
        
        latest_block = int(latest_block_hex, 16)
        tx_block = int(block_number_hex, 16)
        confirmations = latest_block - tx_block
        
        if confirmations >= ERC20_CONFIRMATIONS:
            return {"success": True, "confirmations": confirmations}
        else:
            return {
                "success": False,
                "status": "pending",
                "error": f"Мало подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}",
                "confirmations": confirmations
            }
        
async def check_transaction_stages(tx_hash: str, target_address: str, stage_set: set) -> dict:
    """Проверяет транзакцию по этапам и возвращает статусы"""

    
    async with aiohttp.ClientSession() as session:
        response = await fetch_transaction(session, tx_hash)
        await asyncio.sleep(1)
        if not response["success"]:
            return response

        tx_data = response["data"]
        # Этап 1: Проверка включения в блок
        if "in_block" in stage_set:
            in_block = await check_in_block(tx_data, tx_hash)
            logger.info(f"[ethereum] --in_block-- {in_block} ")
            
            if not in_block["success"]:
                stage_set.add("in_block")
                # result_transaction.update({**in_block})
                return {"stage": stage_set, **in_block}
            else:
                stage_set.discard("in_block")
        

        # Этап 2: Проверка, что это USDT
        if "is_erc20" in stage_set:
            is_erc20 = await check_is_erc20(tx_data, tx_hash)
            logger.info(f"[ethereum] --is_erc20-- {is_erc20} ")
            if not is_erc20["success"]:
                stage_set.add("is_erc20")
                # result_transaction.update({**is_erc20})
                return {"stage": stage_set, **is_erc20}
            else:
                stage_set.discard("is_erc20")
        

        # Этап 3: Проверка получателя
        if "recipient" in stage_set:
            recipient = await check_recipient(tx_data, target_address)
            logger.info(f"[ethereum] --recipient-- {recipient} ")
            if not recipient["success"]:
                stage_set.add("recipient")
                # result_transaction.update({"amount": recipient.get("amount", "N/A"), **recipient})
                return {"stage": stage_set, **recipient}
            else:
                stage_set.discard("recipient")
        

        # Этап 4: Проверка подтверждений
        if "confirmations" in stage_set:
            blockNumber_hex = tx_data.get("blockNumber")
            logger.info(f"[ethereum] --recipient-- {blockNumber_hex}")
            confirmations = await check_confirmations(session, blockNumber_hex)
            await asyncio.sleep(1)
            logger.info(f"[ethereum] --confirmations-- {confirmations} ")
            if not confirmations["success"]:
                stage_set.add("confirmations")
                # result_transaction.update({**confirmations})
                return {"stage": stage_set, **confirmations}
            else:
                stage_set.discard("confirmations")

         
        # result_transaction.update({
        #     "stage": stage_list                       
        # })
        
        if len(stage_set) == 0:
            status = "confirmed"
            success = True
            stage_set.add("completed")

        else:
            status = "pending"
            success = False
            
        stage_list = list(stage_set)   
        logger.info(f"[ethereum] --result_transaction-- {stage_list}")
        return {
                "status": status,
                "success": success,
                "stage": stage_list
            }