# networks/tron.py
import json
import aiohttp
import datetime
import json
import re
from typing import Optional, Dict, Any

from config import TRONSCAN_API, TRC20_CONFIRMATIONS, USDT_TRC20_CONTRACT, TRONSCAN_API_KEY, logger
from utils.extract_hash_in_url import extract_tx_hash


USDT_CONTRACT = USDT_TRC20_CONTRACT


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


def _ok(stage=None, **extra):
    return {"success": True, "status": "confirmed", "code": TxCode.OK, "stage": stage or ["completed"], **extra}


def _failed(code, stage=None, **extra):
    return {"success": False, "status": "failed", "code": code, "stage": stage or ["failed"], **extra}


def _pending(code, stage=None, **extra):
    return {"success": False, "status": "pending", "code": code, "stage": stage or ["pending"], **extra}

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

async def get_client_session():
    """
    Возвращает aiohttp.ClientSession с таймаутом для использования в мониторинге.
    Внимание: вызывающая сторона отвечает за закрытие сессии.
    """
    timeout = aiohttp.ClientTimeout(total=10)
    return aiohttp.ClientSession(timeout=timeout)


async def _get(session, url: str, params: dict, retries: int = 3) -> dict:
    last_err = None
    for i in range(retries):
        try:
            headers = {}
            if TRONSCAN_API_KEY:
                headers["TRON-PRO-API-KEY"] = TRONSCAN_API_KEY
            async with session.get(url, params=params, headers=headers) as resp:
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
    """Получает транзакцию по хешу из TronGrid или TronScan (в зависимости от TRONSCAN_API)."""
    base = TRONSCAN_API.lower()
    # Ветка TronGrid
    if "trongrid" in base:
        url = f"{TRONSCAN_API}/wallet/gettransactionbyid"
        params = {"value": tx_hash}
        data = await _get(session, url, params)
        if not data or "error" in data:
            return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка API"))
        if data.get("confirmed") is not True:
            return _pending(TxCode.NOT_CONFIRMED, error="Транзакция не подтверждена")
        return {"success": True, "data": data}

    # Ветка TronScan (apilist.tronscanapi.com)
    url = f"{TRONSCAN_API}/api/transaction-info"
    params = {"hash": tx_hash}
    data = await _get(session, url, params)
    if not data or "error" in data:
        return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка API"))
    # Приведем формат к единому виду: добавим поля для совместимости
    # TronScan возвращает tokenTransferInfo (объект)
    tti = data.get("tokenTransferInfo") or {}
    data.setdefault("trc20TransferInfo", [{
        "contract_address": tti.get("contract_address"),
        "to_address": tti.get("to_address"),
        "from_address": tti.get("from_address"),
        "amount_str": str(tti.get("amount_str", "0")),
        "decimals": tti.get("decimals", 6)
    }])
    # Условно подтверждено, если confirmed==True или блок есть
    if not data.get("confirmed", True):
        return _pending(TxCode.NOT_CONFIRMED, error="Транзакция не подтверждена")
    return {"success": True, "data": data}


def check_confirmations(data: dict) -> Dict[str, Any]:
    confirmations = data.get("confirmations", 0)
    if confirmations < TRC20_CONFIRMATIONS:
        logger.info("[tron] confirmations: %s",confirmations)
        return _pending(
            TxCode.LOW_CONFIRMATIONS,
            stage=["confirmations"],
            error=f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}",
            confirmations=confirmations
        )
    return {"success": True, "confirmations": confirmations}


def check_contract_and_transfer(data: dict, target_address: str) -> Dict[str, Any]:
    transfers = data.get("trc20TransferInfo", [])
    if not transfers:
        return _failed(TxCode.NO_TRANSFERS, stage=["contract_check"], error="Транзакция не содержит переводов USDT (TRC20). Возможно, это перевод TRX или другого токена.")

    transfer = transfers[0]
    logger.info("[tron] Transfer info: %s", transfer)

    if transfer.get("contract_address") != USDT_CONTRACT:
        logger.info("[tron] contract_address: %s", transfer.get("contract_address"))
        return _failed(TxCode.INVALID_TOKEN, stage=["contract_check"], error=f"Не USDT (TRC20). Контракт: {transfer.get('contract_address')}, ожидаемый: {USDT_CONTRACT}")

    if transfer.get("to_address") != target_address:
        logger.info("[tron] to_address: %s", transfer.get("to_address"))
        return _failed(
            TxCode.INVALID_RECIPIENT,
            stage=["recipient_check"],
            error=f"Токены отправлены на другой адрес: {transfer.get('to_address')}"
        )

    return {"success": True, "transfer": transfer}


async def check_tron_transaction(user_input: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет TRC20 USDT транзакцию в сети Tron.
    Возвращает информацию о транзакции даже если она еще не полностью подтверждена.
    """
    logger.info("Starting TRON transaction check. Input: %s, Target: %s", user_input, target_address)
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
                    stage=["contract_execution"],
                    error=f"Ошибка исполнения контракта: {data.get('contractRet')}"
                )

            # Проверка токена и получателя (это можно проверить сразу)
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
            
            # Проверка подтверждений
            conf_resp = check_confirmations(data)
            if not conf_resp["success"]:
                # Транзакция найдена, но недостаточно подтверждений
                # Возвращаем информацию о транзакции с статусом "pending"
                return _pending(
                    conf_resp["code"],
                    stage=conf_resp.get("stage", ["confirmations"]),
                    amount=amount,
                    from_address=transfer.get("from_address", ""),
                    to_address=transfer.get("to_address", ""),
                    timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                    confirmations=data.get("confirmations", 0),
                    error=conf_resp.get("error", "")
                )

            # Все проверки пройдены, транзакция подтверждена
            logger.info("[tron] Transaction confirmed: %s", tx_hash)
            return _ok(
                stage=["completed"],
                amount=amount,
                from_address=transfer.get("from_address", ""),
                to_address=transfer.get("to_address", ""),
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                confirmations=conf_resp["confirmations"]
            )

    except Exception as e:
        logger.exception("[tron] Internal error")
        return _failed(TxCode.INTERNAL_ERROR, stage=["internal_error"], error=str(e))


# =============================================================================
# ФУНКЦИИ ДЛЯ МОНИТОРИНГА ТРАНЗАКЦИЙ
# =============================================================================

async def get_recent_transactions(session, wallet_address: str, limit: int = 50) -> Dict[str, Any]:
    """Получает последние входящие TRC20 USDT для кошелька из TronGrid или TronScan."""
    try:
        base = TRONSCAN_API.lower()
        # TronGrid
        if "trongrid" in base:
            url = f"{TRONSCAN_API}/v1/accounts/{wallet_address}/transactions/trc20"
            params = {
                "limit": limit,
                "order_by": "block_timestamp,desc",
                "contract_address": USDT_CONTRACT
            }
            data = await _get(session, url, params)
            if not data or "error" in data:
                return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка получения транзакций"))
            transactions = data.get("data", [])
            logger.info(f"[tron] Получено {len(transactions)} транзакций от TronGrid API")
            return {"success": True, "data": {"data": transactions}}

        # TronScan
        url = f"{TRONSCAN_API}/api/token_trc20/transfers"
        params = {
            "toAddress": wallet_address,
            "limit": limit,
            "contract": USDT_CONTRACT,
            "start": 0,
            "sort": "desc"
        }
        data = await _get(session, url, params)
        if not data or "error" in data:
            return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка получения транзакций"))
        items = data.get("token_transfers") or data.get("data") or []
        # Приведем к единому формату, похожему на TronGrid
        normalized = []
        for it in items:
            normalized.append({
                "transaction_id": it.get("transaction_id") or it.get("hash"),
                "to": it.get("to_address") or it.get("to"),
                "from": it.get("from_address") or it.get("from"),
                "value": int(it.get("quant", it.get("amount", it.get("value", 0)))) if str(it.get("quant", "")).isdigit() else int(it.get("amount_str", it.get("value", 0)) or 0),
                "token_info": {"decimals": it.get("decimals", 6)},
                "block_timestamp": it.get("block_ts") or it.get("timestamp") or 0
            })
        logger.info(f"[tron] Получено {len(normalized)} транзакций от TronScan API")
        return {"success": True, "data": {"data": normalized}}
    except Exception as e:
        logger.error(f"[tron] Ошибка получения транзакций: {e}")
        return _failed(TxCode.INTERNAL_ERROR, error=str(e))

async def get_transaction_by_hash(session, tx_hash: str) -> Dict[str, Any]:
    """
    Получает транзакцию по хешу
    """
    try:
        url = f"{TRONSCAN_API}/wallet/gettransactionbyid"
        params = {"value": tx_hash}
        
        data = await _get(session, url, params)
        
        if not data or "error" in data:
            return _failed(TxCode.API_ERROR, error=data.get("error", "Ошибка получения транзакции"))
        
        return {"success": True, "data": data}
        
    except Exception as e:
        logger.error(f"[tron] Ошибка получения транзакции: {e}")
        return _failed(TxCode.INTERNAL_ERROR, error=str(e))

async def check_transaction_for_pin_match(session, tx_hash: str, target_wallet: str, 
                                         expected_amount: float, pin_code: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию на соответствие PIN-коду
    Записывает хеш сразу при обнаружении транзакции, даже если недостаточно подтверждений
    """
    try:
        # Получаем транзакцию
        tx_resp = await get_transaction_by_hash(session, tx_hash)
        if not tx_resp["success"]:
            return tx_resp
        
        data = tx_resp["data"]
        
        # Проверяем токен и получателя (это можно проверить сразу)
        token_resp = check_contract_and_transfer(data, target_wallet)
        if not token_resp["success"]:
            return token_resp
        
        transfer = token_resp["transfer"]
        
        # Проверяем сумму (с небольшой погрешностью)
        raw_amount = int(transfer.get("amount_str", "0"))
        decimals = int(transfer.get("decimals", 6))
        amount = raw_amount / (10 ** decimals)
        
        # Проверяем соответствие суммы (с погрешностью 0.01 USDT)
        logger.info(f"[tron] Проверяем сумму: {amount} vs ожидаемая: {expected_amount}")
        if abs(amount - expected_amount) > 0.01:
            logger.info(f"[tron] Сумма не соответствует: {amount} != {expected_amount}")
            return _failed(
                TxCode.INVALID_RECIPIENT,
                error=f"Сумма не соответствует ожидаемой: {amount} != {expected_amount}"
            )
        
        logger.info(f"[tron] Сумма соответствует PIN-коду {pin_code}")
        
        # Проверяем, что транзакция подтверждена
        if data.get("confirmed") is not True:
            # Транзакция найдена и соответствует PIN-коду, но не подтверждена
            timestamp_ms = data.get("timestamp", 0)
            dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            
            return _pending(
                TxCode.NOT_CONFIRMED,
                amount=amount,
                from_address=transfer.get("from_address", ""),
                to_address=transfer.get("to_address", ""),
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                confirmations=data.get("confirmations", 0),
                pin_code=pin_code,
                error="Транзакция не подтверждена"
            )
        
        # Упрощенная проверка: если сумма и адрес совпадают, считаем транзакцию соответствующей PIN-коду
        # Комментарий с PIN-кодом не обязателен для автоматического обнаружения
        
        timestamp_ms = data.get("timestamp", 0)
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
        
        # Проверяем подтверждения
        conf_resp = check_confirmations(data)
        if not conf_resp["success"]:
            # Транзакция найдена и соответствует PIN-коду, но недостаточно подтверждений
            # Возвращаем информацию о транзакции с статусом "pending"
            return _pending(
                conf_resp["code"],
                amount=amount,
                from_address=transfer.get("from_address", ""),
                to_address=transfer.get("to_address", ""),
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                confirmations=data.get("confirmations", 0),
                pin_code=pin_code,
                error=conf_resp.get("error", "")
            )
        
        # Все проверки пройдены, транзакция подтверждена
        return _ok(
            amount=amount,
            from_address=transfer.get("from_address", ""),
            to_address=transfer.get("to_address", ""),
            timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
            confirmations=conf_resp["confirmations"],
            pin_code=pin_code
        )
        
    except Exception as e:
        logger.error(f"[tron] Ошибка проверки транзакции для PIN: {e}")
        return _failed(TxCode.INTERNAL_ERROR, error=str(e))

async def monitor_wallet_for_new_transactions(session, wallet_address: str, 
                                            active_pins: list) -> Dict[str, Any]:
    """
    Мониторит кошелек на предмет новых транзакций, соответствующих активным PIN-кодам
    """
    try:
        # Получаем последние транзакции
        tx_resp = await get_recent_transactions(session, wallet_address, limit=20)
        if not tx_resp["success"]:
            return tx_resp
        
        transactions = tx_resp["data"].get("data", [])
        matched_transactions = []
        
        logger.info(f"[tron] Получено {len(transactions)} транзакций для мониторинга {wallet_address}")
        
        for tx in transactions:
            tx_hash = tx.get("transaction_id")
            if not tx_hash:
                continue
            
            logger.info(f"[tron] Проверяем транзакцию: {tx_hash}")
            
            # Проверяем каждую транзакцию против активных PIN-кодов
            for pin_data in active_pins:
                pin_code = pin_data.get("pin_code")
                raw_amount = str(pin_data.get("amount", "0")).strip()
                # Надёжный парсер суммы: поддержка запятой и точки
                cleaned = raw_amount.replace(" ", "")
                if "," in cleaned and "." not in cleaned:
                    cleaned = cleaned.replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
                try:
                    expected_amount = float(cleaned)
                except Exception:
                    try:
                        expected_amount = float(str(raw_amount).replace(",", ""))
                    except Exception:
                        expected_amount = 0.0
                
                if not pin_code or expected_amount <= 0:
                    continue
                
                # Проверяем, что это TRC20 транзакция к нашему адресу
                if tx.get("to") != wallet_address:
                    # подробный лог для диагностики несовпадения адреса
                    logger.info(f"[tron] skip: to={tx.get('to')} != wallet={wallet_address}")
                    continue

                # Если в PIN есть кошелек пользователя, проверяем отправителя
                expected_from = (pin_data.get("user_wallet") or "").strip()
                if expected_from:
                    if tx.get("from") != expected_from:
                        logger.info(f"[tron] skip: from={tx.get('from')} != expected_from={expected_from}")
                        continue
                
                # Проверяем сумму
                tx_value = int(tx.get("value", 0))
                decimals = tx.get("token_info", {}).get("decimals", 6)
                tx_amount = tx_value / (10 ** decimals)
                
                logger.info(f"[tron] Проверяем сумму: {tx_amount} vs ожидаемая: {expected_amount}")
                
                if abs(tx_amount - expected_amount) > 0.01:
                    logger.info(f"[tron] skip: amount mismatch tx_amount={tx_amount} expected={expected_amount}")
                    continue
                
                logger.info(f"[tron] Найдена соответствующая транзакция: {tx_hash} для PIN {pin_code}")
                
                # Для TronGrid API все транзакции считаются подтвержденными
                tx_status = "confirmed"
                
                # Конвертируем timestamp
                timestamp_ms = tx.get("block_timestamp", 0)
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                
                matched_transactions.append({
                    "tx_hash": tx_hash,
                    "pin_data": pin_data,
                    "transaction_data": {
                        "status": tx_status,
                        "amount": tx_amount,
                        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "confirmations": 12,  # TronGrid транзакции обычно подтверждены
                        "from_address": tx.get("from"),
                        "to_address": tx.get("to")
                    }
                })
        
        return {
            "success": True,
            "matched_transactions": matched_transactions,
            "total_checked": len(transactions)
        }
        
    except Exception as e:
        logger.error(f"[tron] Ошибка мониторинга кошелька: {e}")
        return _failed(TxCode.INTERNAL_ERROR, error=str(e))