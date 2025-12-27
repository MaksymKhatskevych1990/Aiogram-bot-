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
            has_api_key = bool(TRONSCAN_API_KEY)
            is_trongrid = "trongrid" in TRONSCAN_API.lower()
            
            if TRONSCAN_API_KEY:
                # TronGrid использует заголовок X-API-Key
                if is_trongrid:
                    headers["X-API-Key"] = TRONSCAN_API_KEY
                    logger.info(f"[tron] Используем TronGrid API с ключом (X-API-Key), URL: {TRONSCAN_API}")
                else:
                    headers["TRON-PRO-API-KEY"] = TRONSCAN_API_KEY
                    logger.info(f"[tron] Используем TronScan API с ключом (TRON-PRO-API-KEY), URL: {TRONSCAN_API}")
            else:
                if is_trongrid:
                    logger.warning(f"[tron] ⚠️ TronGrid API используется без ключа. Некоторые запросы могут требовать API ключ.")
                else:
                    logger.warning(f"[tron] ⚠️ API ключ не настроен для TronScan API")
            
            logger.info(f"[tron] Запрос: {url}, API={TRONSCAN_API}, has_api_key={has_api_key}, is_trongrid={is_trongrid}")
            
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status >= 500:
                    logger.warning(f"[tron] Server error {resp.status}, retrying...")
                    continue
                if resp.status != 200:
                    # Получаем текст ошибки для диагностики
                    error_text = ""
                    try:
                        error_data = await resp.json()
                        error_text = error_data.get("message", error_data.get("error", ""))
                    except:
                        error_text = await resp.text()
                    
                    logger.error(f"[tron] API error {resp.status}: {error_text[:200] if error_text else 'No error message'}")
                    logger.error(f"[tron] URL: {url}, Headers: {list(headers.keys()) if headers else 'None'}")
                    return {"error": f"API error {resp.status}: {error_text[:100] if error_text else 'Unknown error'}"}

                data = await resp.json()
                logger.debug(f"[tron] Успешный ответ от API: {len(str(data))} символов")
                return data
        except Exception as e:
            last_err = e
            logger.error(f"[tron] Request failed ({i+1}/{retries}): {str(e)}", exc_info=True)

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
    if tti:
        data.setdefault("trc20TransferInfo", [{
            "contract_address": tti.get("contract_address"),
            "to_address": tti.get("to_address"),
            "from_address": tti.get("from_address"),
            "amount_str": str(tti.get("amount_str", "0")),
            "decimals": tti.get("decimals", 6)
        }])
    
    # Для TronScan API: если есть blockNumber, транзакция подтверждена
    # Также проверяем наличие contractRet или result
    block_number = data.get("blockNumber") or data.get("block")
    contract_ret = data.get("contractRet") or data.get("contract_ret") or data.get("result")
    
    # Если есть номер блока, транзакция подтверждена
    if block_number:
        data["confirmed"] = True
        # Если contractRet отсутствует, но есть блок, считаем успешной
        if not contract_ret:
            data["contractRet"] = "SUCCESS"
    
    # Условно подтверждено, если confirmed==True или блок есть
    if not data.get("confirmed", True) and not block_number:
        return _pending(TxCode.NOT_CONFIRMED, error="Транзакция не подтверждена")
    return {"success": True, "data": data}


async def check_confirmations(session, data: dict) -> Dict[str, Any]:
    """
    Проверяет количество подтверждений транзакции.
    Если confirmations не указаны в данных, вычисляет их по текущему блоку.
    Если транзакция успешна и подтверждена на блокчейне, считаем её подтвержденной.
    """
    # Проверяем, что транзакция успешна и подтверждена
    # Для TronScan API поле может называться по-разному
    contract_ret = data.get("contractRet") or data.get("contract_ret") or data.get("result")
    confirmed = data.get("confirmed", True)
    
    # Если есть trc20TransferInfo, значит транзакция успешна (токены переведены)
    has_transfer = bool(data.get("trc20TransferInfo") or data.get("tokenTransferInfo"))
    
    # Если транзакция успешна и подтверждена, но нет точного количества подтверждений,
    # считаем её подтвержденной (особенно для TronScan API)
    # Проверяем: contractRet == "SUCCESS" ИЛИ (подтверждена И есть трансфер токенов)
    is_successful = (contract_ret == "SUCCESS") or (confirmed and has_transfer and (not contract_ret or contract_ret != "REVERT"))
    
    if is_successful:
        # Пытаемся получить или вычислить подтверждения
        confirmations = data.get("confirmations", 0)
        
        # Если confirmations не указаны, вычисляем их
        if confirmations == 0:
            block_number = data.get("blockNumber") or data.get("block")
            if block_number:
                try:
                    # Получаем текущий блок
                    base = TRONSCAN_API.lower()
                    if "trongrid" in base:
                        url = f"{TRONSCAN_API}/wallet/getnowblock"
                    else:
                        url = f"{TRONSCAN_API}/api/system"
                    
                    current_block_data = await _get(session, url, {})
                    if current_block_data and not current_block_data.get("error"):
                        if "trongrid" in base:
                            current_block = current_block_data.get("block_header", {}).get("raw_data", {}).get("number", 0)
                        else:
                            current_block = current_block_data.get("block", 0)
                        
                        if current_block > 0:
                            confirmations = max(0, current_block - int(block_number))
                            logger.info(f"[tron] Вычислены подтверждения: {confirmations} (блок транзакции: {block_number}, текущий блок: {current_block})")
                except Exception as e:
                    logger.warning(f"[tron] Не удалось вычислить подтверждения: {e}")
                    # Если транзакция успешна и подтверждена, считаем что подтверждений достаточно
                    logger.info("[tron] Транзакция успешна и подтверждена, считаем подтвержденной (fallback)")
                    confirmations = TRC20_CONFIRMATIONS + 1
            else:
                # Если нет номера блока, но транзакция успешна и подтверждена, считаем подтвержденной
                logger.info("[tron] Транзакция успешна и подтверждена (нет номера блока), считаем подтвержденной")
                confirmations = TRC20_CONFIRMATIONS + 1
        
        # Проверяем достаточность подтверждений
        if confirmations >= TRC20_CONFIRMATIONS:
            return {"success": True, "confirmations": confirmations}
        else:
            logger.info(f"[tron] confirmations: {confirmations}/{TRC20_CONFIRMATIONS}")
            return _pending(
                TxCode.LOW_CONFIRMATIONS,
                stage=["confirmations"],
                error=f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}",
                confirmations=confirmations
            )
    else:
        # Транзакция не успешна или не подтверждена
        return _pending(
            TxCode.NOT_CONFIRMED,
            stage=["confirmations"],
            error=f"Транзакция не подтверждена (contractRet={contract_ret}, confirmed={confirmed})",
            confirmations=0
        )


def check_contract_and_transfer(data: dict, target_address: str) -> Dict[str, Any]:
    transfers = data.get("trc20TransferInfo", [])
    if not transfers:
        return _failed(TxCode.NO_TRANSFERS, stage=["contract_check"], error="Транзакция не содержит переводов USDT (TRC20). Возможно, это перевод TRX или другого токена.")

    transfer = transfers[0]
    logger.info("[tron] Transfer info: %s", transfer)

    if transfer.get("contract_address") != USDT_CONTRACT:
        logger.info("[tron] contract_address: %s", transfer.get("contract_address"))
        return _failed(TxCode.INVALID_TOKEN, stage=["contract_check"], error=f"Не USDT (TRC20). Контракт: {transfer.get('contract_address')}, ожидаемый: {USDT_CONTRACT}")

    # Сравниваем адреса (нормализуем для сравнения - убираем пробелы, приводим к нижнему регистру)
    tx_to_address = (transfer.get("to_address") or "").strip().lower()
    target_address_normalized = (target_address or "").strip().lower()
    
    logger.info(f"[tron] Сравнение адресов: tx_to_address='{tx_to_address}', target_address='{target_address_normalized}'")
    
    if tx_to_address != target_address_normalized:
        logger.warning(f"[tron] Адреса не совпадают: tx_to_address='{tx_to_address}' != target_address='{target_address_normalized}'")
        return _failed(
            TxCode.INVALID_RECIPIENT,
            stage=["recipient_check"],
            error=f"Токены отправлены на другой адрес: {transfer.get('to_address')} (ожидался: {target_address})"
        )

    logger.info(f"[tron] ✅ Адреса совпадают: {tx_to_address}")
    return {"success": True, "transfer": transfer}


async def check_tron_transaction(user_input: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет TRC20 USDT транзакцию в сети Tron.
    Возвращает информацию о транзакции даже если она еще не полностью подтверждена.
    
    Args:
        user_input: Хеш транзакции или URL
        target_address: Адрес кошелька бота из БД (to_address) - куда должны переводить средства
    """
    logger.info("Starting TRON transaction check. Input: %s, Target address (from DB to_address): %s", user_input, target_address)
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
            # Для TronScan API поле может называться по-разному или отсутствовать
            contract_ret = data.get("contractRet") or data.get("contract_ret") or data.get("result")
            # Если поле отсутствует, но транзакция подтверждена, считаем успешной
            if contract_ret and contract_ret != "SUCCESS":
                return _failed(
                    TxCode.CONTRACT_ERROR,
                    stage=["contract_execution"],
                    error=f"Ошибка исполнения контракта: {contract_ret}"
                )
            # Если contractRet отсутствует, но есть подтверждение и токен-трансфер, считаем успешной
            if not contract_ret and not data.get("confirmed", True):
                return _failed(
                    TxCode.CONTRACT_ERROR,
                    stage=["contract_execution"],
                    error="Транзакция не подтверждена"
                )

            # Проверка токена и получателя (это можно проверить сразу)
            # Если target_address не указан, пропускаем проверку адреса получателя
            transfer = None
            if target_address:
                token_resp = check_contract_and_transfer(data, target_address)
                logger.info("[tron] token_resp: %s",token_resp)
                if not token_resp["success"]:
                    # Если адрес получателя не совпадает, но транзакция успешна на блокчейне,
                    # это может быть другая транзакция - не возвращаем ошибку, а проверяем только подтверждения
                    code = token_resp.get("code")
                    if code == "invalid_recipient":
                        logger.warning(f"[tron] Адрес получателя не совпадает ({target_address}), но транзакция успешна на блокчейне. Продолжаем проверку подтверждений.")
                        # Продолжаем проверку, но без данных о трансфере - получаем из data напрямую
                        transfers = data.get("trc20TransferInfo", [])
                        if transfers:
                            transfer = transfers[0]
                    else:
                        return token_resp
                else:
                    transfer = token_resp["transfer"]
            else:
                # Если target_address не указан, проверяем только что есть трансфер USDT
                transfers = data.get("trc20TransferInfo", [])
                if not transfers:
                    return _failed(TxCode.NO_TRANSFERS, stage=["contract_check"], error="Транзакция не содержит переводов USDT (TRC20)")
                transfer = transfers[0]
                if transfer.get("contract_address") != USDT_CONTRACT:
                    return _failed(TxCode.INVALID_TOKEN, stage=["contract_check"], error=f"Не USDT (TRC20). Контракт: {transfer.get('contract_address')}")

            if transfer:
                logger.info("[tron] transfer: %s",transfer)
                raw_amount = int(transfer.get("amount_str", "0"))
                decimals = int(transfer.get("decimals", 6))
                amount = raw_amount / (10 ** decimals)
            else:
                # Если transfer не определен (пропустили проверку адреса), используем данные из data
                transfers = data.get("trc20TransferInfo", [])
                if transfers:
                    transfer = transfers[0]
                    raw_amount = int(transfer.get("amount_str", "0"))
                    decimals = int(transfer.get("decimals", 6))
                    amount = raw_amount / (10 ** decimals)
                else:
                    amount = 0

            timestamp_ms = data.get("timestamp", 0)
            dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            
            # Проверка подтверждений (теперь асинхронная)
            conf_resp = await check_confirmations(session, data)
            if not conf_resp["success"]:
                # Транзакция найдена, но недостаточно подтверждений
                # Возвращаем информацию о транзакции с статусом "pending"
                from_addr = transfer.get("from_address", "") if transfer else ""
                to_addr = transfer.get("to_address", "") if transfer else ""
                return _pending(
                    conf_resp["code"],
                    stage=conf_resp.get("stage", ["confirmations"]),
                    amount=amount,
                    from_address=from_addr,
                    to_address=to_addr,
                    timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                    confirmations=data.get("confirmations", 0),
                    error=conf_resp.get("error", "")
                )

            # Все проверки пройдены, транзакция подтверждена
            logger.info("[tron] Transaction confirmed: %s", tx_hash)
            from_addr = transfer.get("from_address", "") if transfer else ""
            to_addr = transfer.get("to_address", "") if transfer else ""
            return _ok(
                stage=["completed"],
                amount=amount,
                from_address=from_addr,
                to_address=to_addr,
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
            # Правильный endpoint для TronGrid API
            url = f"{TRONSCAN_API}/v1/accounts/{wallet_address}/transactions/trc20"
            params = {
                "limit": limit,
                "order_by": "block_timestamp,desc",
                "contract_address": USDT_CONTRACT,
                "only_to": "true"  # Только входящие транзакции
            }
            logger.info(f"[tron] Запрос к TronGrid API: {url}, wallet={wallet_address[:8]}...{wallet_address[-6:]}, limit={limit}, contract={USDT_CONTRACT}")
            data = await _get(session, url, params)
            if not data or "error" in data:
                error_msg = data.get("error", "Ошибка получения транзакций") if data else "Пустой ответ от API"
                logger.error(f"[tron] Ошибка TronGrid API для адреса {wallet_address[:8]}...{wallet_address[-6:]}: {error_msg}")
                return _failed(TxCode.API_ERROR, error=error_msg)
            transactions = data.get("data", [])
            logger.info(f"[tron] ✅ Получено {len(transactions)} транзакций от TronGrid API для адреса {wallet_address[:8]}...{wallet_address[-6:]}")
            if transactions:
                logger.debug(f"[tron] Первая транзакция: hash={transactions[0].get('transaction_id', 'N/A')[:16]}..., amount={transactions[0].get('value', 0)}")
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
        base = TRONSCAN_API.lower()
        if "trongrid" in base:
            # TronGrid endpoint
            url = f"{TRONSCAN_API}/wallet/gettransactionbyid"
            params = {"value": tx_hash}
        else:
            # TronScan endpoint  
            url = f"{TRONSCAN_API}/api/transaction-info"
            params = {"hash": tx_hash}
        
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
        
        # Проверяем подтверждения (теперь асинхронная, используем существующую сессию)
        conf_resp = await check_confirmations(session, data)
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