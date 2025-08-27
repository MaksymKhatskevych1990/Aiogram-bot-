# tron.py
import aiohttp
import datetime
from typing import Optional, Dict, Any

from config import TRONSCAN_API, TRC20_CONFIRMATIONS, logger
from utils.extract_hash_in_url import extract_tx_hash


USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


async def check_tron_transaction(user_input: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию TRC20 USDT на адресе Tron.
    """
    logger.info("Starting TRON transaction check. Input: %s, Target: %s", user_input, target_address)
    tx_hash: Optional[str] = extract_tx_hash(user_input)
    if not tx_hash:
        return {"success": False, "error": "Введите корректный хеш или ссылку на транзакцию"}
    logger.info("Extracted hash: %s", tx_hash)

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TRONSCAN_API}/transaction-info"
            params = {"hash": tx_hash}

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}

                data = await response.json()
                logger.info("TRON raw data: %s", data)

                if data.get("confirmed") is not True:
                    logger.info("Transaction not confirmed")
                    return {"success": False, "error": "Транзакция не подтверждена"}

                confirmations = int(data.get("confirmations", 0))
                if confirmations < TRC20_CONFIRMATIONS:
                    logger.info("Insufficient confirmations: %s < %s", confirmations, TRC20_CONFIRMATIONS)
                    return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}"}

                if data.get("contractRet") != "SUCCESS":
                    logger.info("Contract execution failed: %s", data.get('contractRet'))
                    return {"success": False, "error": f"Ошибка исполнения контракта: {data.get('contractRet')}"}

                transfers = data.get("trc20TransferInfo", [])
                if not transfers:
                    logger.info("No TRC20 transfers found")
                    return {"success": False, "error": "В транзакции нет TRC20-переводов"}

                transfer = transfers[0]
                logger.info("TRON transfer info: %s", transfer)

                logger.info("Checking contract address: %s vs %s", transfer.get("contract_address"), USDT_CONTRACT)
                if transfer.get("contract_address") != USDT_CONTRACT:
                    return {"success": False, "error": "Транзакция не относится к USDT (TRC20)"}

                logger.info("Checking to_address: %s vs target: %s", transfer.get("to_address"), target_address)
                logger.info("Address comparison: %s == %s = %s", transfer.get("to_address"), target_address, transfer.get("to_address") == target_address)
                if transfer.get("to_address") != target_address:
                    logger.info("Address mismatch - returning error")
                    return {"success": False, "error": "Токены отправлены на другой адрес"}

                logger.info("Processing amount: %s, decimals: %s", transfer.get("amount_str"), transfer.get("decimals"))
                raw_amount = int(transfer.get("amount_str", "0"))
                decimals = int(transfer.get("decimals", 6))
                amount = raw_amount / (10 ** decimals)
                logger.info("Calculated amount: %s", amount)

                logger.info("Processing timestamp: %s", data.get("timestamp"))
                timestamp_ms = int(data.get("timestamp", 0))
                dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                logger.info("Converted timestamp: %s", dt)

                result = {
                    "success": True,
                    "status": "confirmed",
                    "amount": amount,
                    "from": transfer.get("from_address", ""),
                    "to": transfer.get("to_address", ""),
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "confirmations": confirmations
                }
                logger.info("Returning successful result: %s", result)
                return result

    except Exception as e:
        logger.exception("Ошибка при проверке TRON транзакции")
        logger.error("Exception details: %s, Type: %s", str(e), type(e))
        return {"success": False, "error": f"Ошибка проверки транзакции: {str(e)}"}
