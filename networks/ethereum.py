# networks/ethereum.py
import json
import aiohttp
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, USDT_ERC20_CONTRACT, ETHERSCAN_API, logger
from utils.decode_etc20 import decode_erc20_input

USDT_CONTRACT = USDT_ERC20_CONTRACT
ETHERSCAN_URL = ETHERSCAN_API

def hex_to_int(value):
    """Преобразует hex-строку в целое число"""
    if value is None:
        return None
        
    if isinstance(value, int):
        return value
        
    if isinstance(value, str) and value.startswith('0x'):
        try:
            return int(value, 16)
        except (ValueError, TypeError):
            return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

class TxCode:
    OK = "ok"
    PENDING = "pending"
    NOT_FOUND = "not_found"
    NOT_IN_BLOCK = "not_in_block"
    INVALID_TOKEN = "invalid_token"
    INVALID_RECIPIENT = "invalid_recipient"
    LOW_CONFIRMATIONS = "low_confirmations"
    API_ERROR = "api_error"
    DECODE_ERROR = "decode_error"
    INTERNAL_ERROR = "internal_error"

def _ok(**extra):
    return {"success": True, "status": "confirmed", "code": TxCode.OK, **extra}

def _pending(code, stage_left=None, **extra):
    # Поддержка вызовов с именованным аргументом stage
    if stage_left is None:
        stage_left = extra.pop("stage", ["pending"]) or ["pending"]
    return {"success": False, "status": "pending", "code": code, "stage": stage_left, **extra}

def _failed(code, stage_left=None, **extra):
    # Поддержка вызовов с именованным аргументом stage
    if stage_left is None:
        stage_left = extra.pop("stage", ["failed"]) or ["failed"]
    return {"success": False, "status": "failed", "code": code, "stage": stage_left, **extra}

def _expired(stage_left, **extra):
    return {"success": False, "status": "expired", "code": "expired", "stage": stage_left, **extra}


@asynccontextmanager
async def _client_session():
    
    timeout = aiohttp.ClientTimeout(total=10)
    session = aiohttp.ClientSession(timeout=timeout)
    session_id = hex(id(session))
    logger.info(f"[ethereum] +++++Created ClientSession {session_id}")
    try:
        yield session
    finally:
        await session.close()
        logger.info(f"[ethereum] Closed------ ClientSession {session_id}")

async def get_client_session():
    """
    Возвращает aiohttp.ClientSession с таймаутом для использования в мониторинге.
    Внимание: вызывающая сторона отвечает за закрытие сессии.
    """
    timeout = aiohttp.ClientTimeout(total=10)
    return aiohttp.ClientSession(timeout=timeout)

async def _get(session, params, retries=3):
    last_err = None
    for i in range(retries):
        try:
            async with session.get(ETHERSCAN_URL, params=params) as resp:
                if resp.status == 429:
                    logger.warning(f"[ethereum] Rate limit exceeded, retrying in {0.7 * (i+1)}s")
                    await asyncio.sleep(0.7 * (i+1))
                    continue
                if resp.status >= 500:
                    logger.warning(f"[ethereum] Server error {resp.status}, retrying in {0.5 * (i+1)}s")
                    await asyncio.sleep(0.5 * (i+1))
                    continue
                
                data = await resp.json()
            await asyncio.sleep(1)  # Etherscan rate limit
            logger.info(f"[ethereum] ---_get----------------------------------------: {resp.status}")
            return data
        except Exception as e:
            last_err = e
            logger.error(f"[ethereum] Request failed (attempt {i+1}/{retries}): {str(e)}")
            await asyncio.sleep(0.5 * (i+1))
    
    error_msg = f"Etherscan request failed after {retries} retries"
    if last_err:
        error_msg += f": {str(last_err)}"
    logger.error(f"[ethereum] {error_msg}")
    return {"status": "0", "message": "NOTOK", "result": error_msg}

async def fetch_transaction(session, tx_hash: str) -> dict:
    """Получает данные транзакции из Etherscan"""
    params = {
        "module": "proxy", 
        "action": "eth_getTransactionByHash", 
        "txhash": tx_hash, 
        "apikey": ETHERSCAN_API_KEY
    }
    
    try:
        data = await _get(session, params)
        if not data or data.get("status") == "0" or not data.get("result"):
            error = data.get("result", "Transaction not found")
            logger.warning(f"[ethereum] Transaction not found: {error}")
            return {
                "success": False, 
                "status": "pending", 
                "code": TxCode.NOT_FOUND, 
                "error": "Транзакция не найдена"
            }
        
        tx_data = data.get("result")
        return {"success": True, "data": tx_data}
    
    except Exception as e:
        logger.exception(f"[ethereum] Error fetching transaction {tx_hash}")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.API_ERROR, 
            "error": f"Ошибка при получении транзакции: {str(e)}"
        }

async def check_in_block(tx_data) -> dict:
    """Проверяет, что транзакция включена в блок"""
    block_number = tx_data.get("blockNumber")
    if not block_number:
        logger.warning("[ethereum] Transaction not in block")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.NOT_IN_BLOCK, 
            "error": "Транзакция не включена в блок"
        }
    
    # Убедимся, что blockNumber - это число
    block_num = hex_to_int(block_number)
    if block_num is None:
        logger.warning(f"[ethereum] Invalid block number format: {block_number}")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.NOT_IN_BLOCK, 
            "error": "Неверный формат номера блока"
        }
    
    return {"success": True, "blockNumber": block_number}

async def check_timestamp_amount(session, tx_data) -> dict:
    """Проверяет время и сумму транзакции"""
    try:
        decoded = decode_erc20_input(tx_data.get("input", "0x"))
    except Exception as e:
        logger.exception("[ethereum] decode error")
        return {
            "success": False, 
            "status": "failed", 
            "code": TxCode.DECODE_ERROR, 
            "error": f"Ошибка декодирования: {str(e)}"
        }

    if not decoded:
        return {
            "success": False, 
            "status": "failed", 
            "code": TxCode.DECODE_ERROR, 
            "error": "Не удалось декодировать input"
        }

    # USDT имеет 6 знаков после запятой
    amount = decoded["amount"] / 10**6
    logger.info(f"[ethereum] Transaction amount: {amount} USDT")

    # Получаем timestamp блока
    block_number = tx_data["blockNumber"]
    params_block = {
        "module": "proxy", 
        "action": "eth_getBlockByNumber", 
        "tag": block_number, 
        "boolean": "true", 
        "apikey": ETHERSCAN_API_KEY
    }
    
    try:
        block_response = await _get(session, params_block)
        block_data = block_response.get("result") or {}
        ts_hex = block_data.get("timestamp")
        
        if not ts_hex:
            logger.warning(f"[ethereum] No timestamp for block {block_number}")
            return {
                "success": False, 
                "status": "pending", 
                "code": TxCode.API_ERROR, 
                "error": "Нет timestamp блока"
            }
        
        ts_int = hex_to_int(ts_hex)
        if ts_int is None:
            logger.warning(f"[ethereum] Invalid timestamp format: {ts_hex}")
            return {
                "success": False, 
                "status": "pending", 
                "code": TxCode.API_ERROR, 
                "error": "Неверный формат timestamp"
            }
        
        timestamp = datetime.fromtimestamp(ts_int, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return {"success": True, "amount": amount, "timestamp": timestamp}
    
    except Exception as e:
        logger.exception("[ethereum] Error getting block timestamp")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.API_ERROR, 
            "error": f"Ошибка получения времени: {str(e)}"
        }

async def check_is_erc20(tx_data) -> dict:
    """Проверяет, что это ERC-20 транзакция USDT"""
    to_address = tx_data.get("to", "").lower()
    if to_address != USDT_CONTRACT:
        logger.warning(f"[ethereum] Not USDT contract: {to_address} != {USDT_CONTRACT}")
        return {
            "success": False, 
            "status": "failed", 
            "code": TxCode.INVALID_TOKEN, 
            "error": "Не USDT (ERC-20)"
        }
    return {"success": True}

async def check_recipient(tx_data, target_address: str) -> dict:
    """Проверяет, что получатель совпадает с целевым адресом"""
    try:
        decoded = decode_erc20_input(tx_data.get("input", "0x"))
        if not decoded:
            return {
                "success": False, 
                "status": "failed", 
                "code": TxCode.DECODE_ERROR, 
                "error": "Не удалось декодировать input"
            }
        
        recipient = decoded["to"].lower()
        if recipient != target_address.lower():
            logger.warning(f"[ethereum] Invalid recipient: {recipient} != {target_address.lower()}")
            return {
                "success": False, 
                "status": "failed", 
                "code": TxCode.INVALID_RECIPIENT, 
                "error": f"Неправильный адрес. Отправлено на {recipient}"
            }
        return {"success": True}
    
    except Exception as e:
        logger.exception("[ethereum] Error checking recipient")
        return {
            "success": False, 
            "status": "failed", 
            "code": TxCode.DECODE_ERROR, 
            "error": f"Ошибка проверки получателя: {str(e)}"
        }

async def check_confirmations(session, block_number_hex: str) -> dict:
    """Проверяет количество подтверждений транзакции"""
    if not block_number_hex:
        logger.warning("[ethereum] No block number provided for confirmation check")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.NOT_IN_BLOCK, 
            "error": "Нет номера блока"
        }
    
    # Преобразуем номер блока транзакции в число
    tx_block = hex_to_int(block_number_hex)
    if tx_block is None:
        logger.warning(f"[ethereum] Invalid block number format: {block_number_hex}")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.NOT_IN_BLOCK, 
            "error": "Неверный формат номера блока"
        }
    
    # Получаем текущий блок
    latest_resp = await _get(session, {
        "module": "proxy", 
        "action": "eth_blockNumber", 
        "apikey": ETHERSCAN_API_KEY
    })
    
    latest_block_hex = latest_resp.get("result")
    if not latest_block_hex:
        logger.warning(f"[ethereum] Failed to get latest block: {latest_resp}")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.API_ERROR, 
            "error": "Не удалось получить последний блок"
        }
    
    # Преобразуем текущий блок в число
    latest_block = hex_to_int(latest_block_hex)
    if latest_block is None:
        logger.warning(f"[ethereum] Invalid latest block format: {latest_block_hex}")
        return {
            "success": False, 
            "status": "pending", 
            "code": TxCode.API_ERROR, 
            "error": "Неверный формат текущего блока"
        }
    
    # Вычисляем подтверждения
    confirmations = max(0, latest_block - tx_block)
    logger.info(f"[ethereum] Confirmations: {confirmations}/{ERC20_CONFIRMATIONS}")
    
    # Проверяем достаточность подтверждений
    required_confirmations = int(ERC20_CONFIRMATIONS)
    if confirmations >= required_confirmations:
        return {"success": True, "confirmations": confirmations}
    
    return {
        "success": False, 
        "status": "pending", 
        "code": TxCode.LOW_CONFIRMATIONS, 
        "confirmations": confirmations, 
        "error": f"{confirmations}/{required_confirmations}"
    }

async def check_transaction_stages(tx_hash: str, target_address: str, stage_set: set) -> dict:
    """
    Проверяет все этапы транзакции и возвращает результат.
    Возвращает единый результат с нормализованными полями (см. TxCode).
    """
    stage_left = set(stage_set)
    logger.info(f"[ethereum] Starting transaction check for {tx_hash} with stages: {stage_left}")
    
    try:
        async with _client_session() as session:
            # 1. Проверяем наличие транзакции
            tx_resp = await fetch_transaction(session, tx_hash)
            if not tx_resp["success"]:
                logger.warning(f"[ethereum] Transaction fetch failed: {tx_resp.get('error')}")
                return _pending(tx_resp.get("code", TxCode.API_ERROR), list(stage_left), error=tx_resp.get("error"))

            tx = tx_resp["data"]
            logger.info(f"[ethereum] Transaction found: {tx_hash}")

            # 2. Проверяем, что транзакция в блоке
            if "in_block" in stage_left:
                r = await check_in_block(tx)
                logger.info(f"[ethereum] ---in_block--- result: {r}")
                if not r["success"]:
                    return _pending(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("in_block")

            # 3. Проверяем, что это ERC-20 транзакция USDT
            if "is_erc20" in stage_left:
                r = await check_is_erc20(tx)
                logger.info(f"[ethereum] ---is_erc20--- result: {r}")
                if not r["success"]:
                    return _failed(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("is_erc20")

            # 4. Проверяем получателя
            if "recipient" in stage_left:
                r = await check_recipient(tx, target_address)
                logger.info(f"[ethereum] ---recipient--- result: {r}")
                if not r["success"]:
                    return _failed(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("recipient")

            extra = {}
            # 5. Проверяем параметры перевода (сумма и время)
            if "transfer_params" in stage_left:
                r = await check_timestamp_amount(session, tx)
                logger.info(f"[ethereum] ---transfer_params--- result: {r}")
                if not r["success"]:
                    # Это не фатальная ошибка, можно подождать (например, из-за лагов узла)
                    return _pending(r.get("code", TxCode.API_ERROR), list(stage_left), error=r.get("error"))
                extra.update({"timestamp": r["timestamp"], "amount": r["amount"]})
                stage_left.discard("transfer_params")

            # 6. Проверяем подтверждения
            if "confirmations" in stage_left:
                r = await check_confirmations(session, tx.get("blockNumber"))
                logger.info(f"[ethereum] ---confirmations--- result: {r}")
                if not r["success"]:
                    return _pending(
                        r["code"], 
                        list(stage_left), 
                        error=r.get("error"), 
                        confirmations=r.get("confirmations", 0), 
                        **extra
                    )
                extra.update({"confirmations": r["confirmations"]})
                stage_left.discard("confirmations")
            
            # Все проверки пройдены
            result = {
                **_ok(stage=["completed"], **extra)
            }
            logger.info(f"[ethereum] Transaction {tx_hash} confirmed: {result}")
            return result

    except Exception as e:
        logger.exception(f"[ethereum] Internal error checking transaction {tx_hash}")
        return {
            "success": False, 
            "status": "failed", 
            "code": TxCode.INTERNAL_ERROR, 
            "stage": list(stage_left), 
            "error": str(e)
        }


# =============================================================================
# ФУНКЦИИ ДЛЯ МОНИТОРИНГА ТРАНЗАКЦИЙ ERC20
# =============================================================================

async def get_recent_erc20_transactions(session, wallet_address: str, limit: int = 50) -> dict:
    """
    Получает последние ERC20 транзакции для указанного адреса кошелька
    """
    try:
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": USDT_CONTRACT,
            "address": wallet_address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }
        
        # Попытка 1: Etherscan V2 API
        attempts = 3
        data = None
        for i in range(attempts):
            v2_params = {
                **params,
                # для V2 меняется только базовый путь и требуется chainid
                # базовый URL оставляем прежним, но добавим флаг для _get через полный путь
            }
            try:
                # вручную формируем URL V2, т.к. ETHERSCAN_URL указывает на v1
                from yarl import URL
                v2_url = str(URL(ETHERSCAN_URL).with_path("/v2/api"))
                async with session.get(v2_url, params={**v2_params, "chainid": 1, "module": "account", "action": "tokentx"}) as resp:
                    v2_json = await resp.json()
                if v2_json and v2_json.get("status") != "0":
                    data = v2_json
                    break
                msg = (v2_json or {}).get("message", "NOTOK")
                logger.warning(f"[ethereum] V2 account.tokentx NOTOK (try {i+1}/{attempts}): {msg} | {v2_json.get('result')}")
                await asyncio.sleep(1.2 * (i + 1))
            except Exception as _:
                await asyncio.sleep(0.8 * (i + 1))

        # Попытка 2: откат к V1, если V2 не вернула результат
        if data is None:
            for i in range(attempts):
                data = await _get(session, params)
                if data and data.get("status") != "0":
                    break
                msg = (data or {}).get("message", "NOTOK")
                res = (data or {}).get("result", "")
                logger.warning(f"[ethereum] V1 account.tokentx NOTOK (try {i+1}/{attempts}): {msg} | {res}")
                await asyncio.sleep(1.5 * (i + 1))
        
        if not data:
            return _failed(TxCode.API_ERROR, stage=["api_error"], error="empty_response")
        
        if data.get("status") == "0":
            msg = data.get("message", "NOTOK")
            # 'No transactions found' – это не ошибка
            if "No transactions" in (msg or ""):
                return {"success": True, "data": []}
            logger.error(f"[ethereum] Ошибка получения транзакций: {msg} | {data.get('result')}")
            return _failed(TxCode.API_ERROR, stage=["api_error"], error=msg)
        
        transactions = data.get("result", [])
        logger.info(f"[ethereum] Получено {len(transactions)} ERC20 транзакций")
        
        return {"success": True, "data": transactions}
        
    except Exception as e:
        logger.error(f"[ethereum] Ошибка получения ERC20 транзакций: {e}")
        return _failed(TxCode.INTERNAL_ERROR, stage=["internal_error"], error=str(e))

async def get_erc20_transaction_by_hash(session, tx_hash: str) -> dict:
    """
    Получает ERC20 транзакцию по хешу
    """
    try:
        # Сначала получаем транзакцию через eth_getTransactionByHash
        tx_resp = await fetch_transaction(session, tx_hash)
        if not tx_resp["success"]:
            return tx_resp
        
        tx_data = tx_resp["data"]
        
        # Проверяем, что это ERC20 транзакция USDT
        if tx_data.get("to", "").lower() != USDT_CONTRACT:
            return _failed(TxCode.INVALID_TOKEN, stage=["contract_check"], error="Не USDT (ERC20)")
        
        return {"success": True, "data": tx_data}
        
    except Exception as e:
        logger.error(f"[ethereum] Ошибка получения ERC20 транзакции: {e}")
        return _failed(TxCode.INTERNAL_ERROR, stage=["internal_error"], error=str(e))

async def check_erc20_transaction_for_pin_match(session, tx_hash: str, target_wallet: str, 
                                               expected_amount: float, pin_code: str) -> dict:
    """
    Проверяет ERC20 транзакцию на соответствие PIN-коду
    """
    try:
        # Получаем транзакцию
        tx_resp = await get_erc20_transaction_by_hash(session, tx_hash)
        if not tx_resp["success"]:
            return tx_resp
        
        tx_data = tx_resp["data"]
        
        # Проверяем получателя
        recipient_resp = await check_recipient(tx_data, target_wallet)
        if not recipient_resp["success"]:
            return recipient_resp
        
        # Декодируем input для получения суммы
        try:
            decoded = decode_erc20_input(tx_data.get("input", "0x"))
            if not decoded:
                return _failed(TxCode.DECODE_ERROR, stage=["decode_error"], error="Не удалось декодировать input")
            
            amount = decoded["amount"] / 10**6  # USDT имеет 6 знаков после запятой
            
        except Exception as e:
            return _failed(TxCode.DECODE_ERROR, stage=["decode_error"], error=f"Ошибка декодирования: {str(e)}")
        
        # Проверяем соответствие суммы (с погрешностью 0.01 USDT)
        logger.info(f"[ethereum] Проверяем сумму: {amount} vs ожидаемая: {expected_amount}")
        if abs(amount - expected_amount) > 0.01:
            logger.info(f"[ethereum] Сумма не соответствует: {amount} != {expected_amount}")
            return _failed(
                TxCode.INVALID_RECIPIENT,
                stage=["amount_check"],
                error=f"Сумма не соответствует ожидаемой: {amount} != {expected_amount}"
            )
        
        logger.info(f"[ethereum] Сумма соответствует PIN-коду {pin_code}")
        
        # Проверяем, что транзакция в блоке
        block_resp = await check_in_block(tx_data)
        if not block_resp["success"]:
            return block_resp
        
        # Проверяем подтверждения
        conf_resp = await check_confirmations(session, tx_data.get("blockNumber"))
        if not conf_resp["success"]:
            # Получаем timestamp блока
            timestamp_resp = await check_timestamp_amount(session, tx_data)
            timestamp = timestamp_resp.get("timestamp", "N/A") if timestamp_resp.get("success") else "N/A"
            
            return _pending(
                conf_resp["code"],
                stage=conf_resp.get("stage", ["confirmations"]),
                amount=amount,
                from_address=tx_data.get("from", ""),
                to_address=decoded["to"],
                timestamp=timestamp,
                confirmations=conf_resp.get("confirmations", 0),
                pin_code=pin_code,
                error=conf_resp.get("error", "")
            )
        
        # Все проверки пройдены
        timestamp_resp = await check_timestamp_amount(session, tx_data)
        timestamp = timestamp_resp.get("timestamp", "N/A") if timestamp_resp.get("success") else "N/A"
        
        return _ok(
            stage=["completed"],
            amount=amount,
            from_address=tx_data.get("from", ""),
            to_address=decoded["to"],
            timestamp=timestamp,
            confirmations=conf_resp["confirmations"],
            pin_code=pin_code
        )
        
    except Exception as e:
        logger.error(f"[ethereum] Ошибка проверки ERC20 транзакции для PIN: {e}")
        return _failed(TxCode.INTERNAL_ERROR, stage=["internal_error"], error=str(e))

async def monitor_erc20_wallet_for_new_transactions(session, wallet_address: str, 
                                                   active_pins: list) -> dict:
    """
    Мониторит ERC20 кошелек на предмет новых транзакций, соответствующих активным PIN-кодам
    """
    try:
        # Получаем последние транзакции
        tx_resp = await get_recent_erc20_transactions(session, wallet_address, limit=20)
        if not tx_resp["success"]:
            return tx_resp
        
        transactions = tx_resp["data"]
        matched_transactions = []
        
        logger.info(f"[ethereum] Получено {len(transactions)} ERC20 транзакций для мониторинга {wallet_address}")
        
        for tx in transactions:
            tx_hash = tx.get("hash")
            if not tx_hash:
                continue
            
            logger.info(f"[ethereum] Проверяем ERC20 транзакцию: {tx_hash}")
            
            # Проверяем каждую транзакцию против активных PIN-кодов
            for pin_data in active_pins:
                pin_code = pin_data.get("pin_code")
                raw_amount = str(pin_data.get("amount", "0")).strip()
                raw_amount = raw_amount.replace(" ", "")
                if "," in raw_amount and "." not in raw_amount:
                    raw_amount = raw_amount.replace(",", ".")
                else:
                    raw_amount = raw_amount.replace(",", "")
                try:
                    expected_amount = float(raw_amount)
                except ValueError:
                    expected_amount = 0.0
                
                if not pin_code or expected_amount <= 0:
                    continue
                
                # Проверяем, что это входящая транзакция к нашему адресу
                if tx.get("to", "").lower() != wallet_address.lower():
                    continue
                
                # Проверяем сумму
                tx_value = int(tx.get("value", 0))
                decimals = int(tx.get("tokenDecimal", 6))
                tx_amount = tx_value / (10 ** decimals)
                
                logger.info(f"[ethereum] Проверяем сумму: {tx_amount} vs ожидаемая: {expected_amount}")
                
                if abs(tx_amount - expected_amount) > 0.01:
                    continue
                
                logger.info(f"[ethereum] Найдена соответствующая ERC20 транзакция: {tx_hash} для PIN {pin_code}")
                
                # Проверяем подтверждения
                conf_resp = await check_confirmations(session, tx.get("blockNumber"))
                tx_status = "confirmed" if conf_resp.get("success") else "pending"
                
                # Конвертируем timestamp
                timestamp_int = int(tx.get("timeStamp", 0))
                dt = datetime.fromtimestamp(timestamp_int, tz=timezone.utc)
                
                matched_transactions.append({
                    "tx_hash": tx_hash,
                    "pin_data": pin_data,
                    "transaction_data": {
                        "status": tx_status,
                        "amount": tx_amount,
                        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "confirmations": conf_resp.get("confirmations", 0) if conf_resp.get("success") else 0,
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
        logger.error(f"[ethereum] Ошибка мониторинга ERC20 кошелька: {e}")
        return _failed(TxCode.INTERNAL_ERROR, stage=["internal_error"], error=str(e))