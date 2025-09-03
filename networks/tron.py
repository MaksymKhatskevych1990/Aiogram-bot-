# networks/tron.py
import json
import aiohttp
import datetime
from typing import Dict, Any, Optional

from config import TRONSCAN_API, TRC20_CONFIRMATIONS, logger
from utils.extract_hash_in_url import extract_tx_hash


USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


class TxCode:
    OK = "ok"
    NOT_FOUND = "not_found"
    INVALID_TOKEN = "invalid_token"
    INVALID_RECIPIENT = "invalid_recipient"
    LOW_CONFIRMATIONS = "low_confirmations"
    NOT_CONFIRMED = "not_confirmed"
    CONTRACT_ERROR = "contract_error"
    NO_TRANSFERS = "no_transfers"
    API_ERROR = "api_error"
    INTERNAL_ERROR = "internal_error"


def _ok(**extra):
    return {"success": True, "status": "confirmed", "code": TxCode.OK, **extra}


def _failed(code, **extra):
    return {"success": False, "status": "failed", "code": code, **extra}


def _pending(code, **extra):
    return {"success": False, "status": "pending", "code": code, **extra}

from contextlib import asynccontextmanager
@asynccontextmanager
async def _client_session():
    
    timeout = aiohttp.ClientTimeout(total=10)
    session = aiohttp.ClientSession(timeout=timeout)
    session_id = hex(id(session))
    logger.info(f"[tron] +++++Created ClientSession {session_id}")
    try:
        yield session
    finally:
        logger.info(f"[tron] Closed------ ClientSession {session_id}")
        await session.close()


async def _get(session, url: str, params: dict, retries: int = 3) -> dict:
    last_err = None
    for i in range(retries):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status >= 500:
                    logger.warning(f"[tron] Server error {resp.status}, retrying...")
                    continue
                if resp.status != 200:
                    return {"error": f"API error {resp.status}"}

                data = await resp.json()
                return data
        except Exception as e:
            last_err = e
            logger.error(f"[tron] Request failed ({i+1}/{retries}): {str(e)}")

    return {"error": f"TRON request failed: {str(last_err) if last_err else 'unknown'}"}


async def fetch_transaction(session, tx_hash: str) -> Dict[str, Any]:
    """Получает транзакцию из Tronscan API"""
    url = f"{TRONSCAN_API}/transaction-info"
    params = {"hash": tx_hash}
    data = await _get(session, url, params)

    if not data or "error" in data:
        return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка API"))

    if data.get("confirmed") is not True:
        return _pending(TxCode.NOT_CONFIRMED, error="Транзакция не подтверждена")

    return {"success": True, "data": data}


def check_confirmations(data: dict) -> Dict[str, Any]:
    confirmations = data.get("confirmations", 0)
    if confirmations < TRC20_CONFIRMATIONS:
        logger.info("[tron] confirmations: %s",confirmations)
        return _pending(
            TxCode.LOW_CONFIRMATIONS,
            error=f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}",
            confirmations=confirmations
        )
    return {"success": True, "confirmations": confirmations}


def check_contract_and_transfer(data: dict, target_address: str) -> Dict[str, Any]:
    transfers = data.get("trc20TransferInfo", [])
    if not transfers:
        return _failed(TxCode.NO_TRANSFERS, error="Транзакция не содержит переводов USDT (TRC20). Возможно, это перевод TRX или другого токена.")

    transfer = transfers[0]
    logger.info("[tron] Transfer info: %s", transfer)

    if transfer.get("contract_address") != USDT_CONTRACT:
        logger.info("[tron] contract_address: %s", transfer.get("contract_address"))
        return _failed(TxCode.INVALID_TOKEN, error="Не USDT (TRC20)")

    if transfer.get("to_address") != target_address:
        logger.info("[tron] to_address: %s", transfer.get("to_address"))
        return _failed(
            TxCode.INVALID_RECIPIENT,
            error=f"Токены отправлены на другой адрес: {transfer.get('to_address')}"
        )

    return {"success": True, "transfer": transfer}


async def check_tron_transaction(user_input: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет TRC20 USDT транзакцию в сети Tron.
    """
    tx_hash: Optional[str] = extract_tx_hash(user_input)
    if not tx_hash:
        return _failed(TxCode.NOT_FOUND, error="Введите корректный хеш")

    try:
        async with _client_session() as session:
            tx_resp = await fetch_transaction(session, tx_hash)
            if not tx_resp["success"]:
                return tx_resp

            data = tx_resp["data"]

            # Проверка исполнение контракта
            if data.get("contractRet") != "SUCCESS":
                return _failed(
                    TxCode.CONTRACT_ERROR,
                    error=f"Ошибка исполнения контракта: {data.get('contractRet')}"
                )

            # Проверка подтверждений
            conf_resp = check_confirmations(data)
            if not conf_resp["success"]:
                return conf_resp

            # Проверка токена и получателя
            token_resp = check_contract_and_transfer(data, target_address)
            logger.info("[tron] token_resp: %s",token_resp)
            if not token_resp["success"]:
                return token_resp

            transfer = token_resp["transfer"]
            logger.info("[tron] transfer: %s",transfer)
            raw_amount = int(transfer.get("amount_str", "0"))
            decimals = int(transfer.get("decimals", 6))
            amount = raw_amount / (10 ** decimals)

            timestamp_ms = data.get("timestamp", 0)
            dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            sels = _ok(
                amount=amount,
                from_address=transfer.get("from_address", ""),
                to_address=transfer.get("to_address", ""),
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                confirmations=conf_resp["confirmations"]
            )
            logger.info("[tron] sels: %s", sels)
            return _ok(
                amount=amount,
                from_address=transfer.get("from_address", ""),
                to_address=transfer.get("to_address", ""),
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                confirmations=conf_resp["confirmations"]
            )

    except Exception as e:
        logger.exception("[tron] Internal error")
        return _failed(TxCode.INTERNAL_ERROR, error=str(e))
