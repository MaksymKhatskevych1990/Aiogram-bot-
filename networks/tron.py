import aiohttp
import datetime
from config import TRONSCAN_API, TRC20_CONFIRMATIONS, logger


async def check_tron_transaction(tx_hash: str, target_address: str) -> dict:
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TRONSCAN_API}/transaction-info"
            params = {"hash": tx_hash}
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}
                data = await response.json()
                if data.get("confirmed") is not True:
                    return {"success": False, "error": "Транзакция не подтверждена"}
                confirmations = data.get("confirmations", 0)
                if confirmations < TRC20_CONFIRMATIONS:
                    return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}"}
                if data.get("contractRet") != "SUCCESS":
                    return {"success": False, "error": f"Ошибка исполнения: {data.get('contractRet')}"}
                transfers = data.get("trc20TransferInfo", [])
                if not transfers:
                    return {"success": False, "error": "Нет TRC20-переводов в транзакции"}
                transfer = transfers[0]
                logger.info("Получен transfer: %s", transfer)
                if transfer["to_address"] != target_address:
                    return {"success": False, "error": "Транзакция направлена на другой адрес"}
                if transfer["contract_address"] != USDT_CONTRACT:
                    return {"success": False, "error": "Неверный токен. Ожидается USDT (TRC20)"}
                raw_value = int(transfer["amount_str"])
                decimals = int(transfer["decimals"])
                value = raw_value / 10**decimals
                timestamp = data.get("timestamp", 0)
                dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                return {
                    "success": True,
                    "status": "confirmed",
                    "amount": value,
                    "from": transfer.get("from_address", ""),
                    "to": transfer.get("to_address", ""),
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "confirmations": confirmations
                }
    except Exception as e:
        return {"success": False, "error": f"Ошибка проверки транзакции: {str(e)}"} 