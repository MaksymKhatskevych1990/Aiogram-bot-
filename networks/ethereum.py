# networks/ethereum.py
import json
import aiohttp
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input

USDT_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec7".lower()
ETHERSCAN_URL = "https://api.etherscan.io/api"

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

def _pending(code, stage_left, **extra):
    return {"success": False, "status": "pending", "code": code, "stage": stage_left, **extra}

def _failed(code, stage_left, **extra):
    return {"success": False, "status": "failed", "code": code, "stage": stage_left, **extra}

def _expired(stage_left, **extra):
    return {"success": False, "status": "expired", "code": "expired", "stage": stage_left, **extra}


@asynccontextmanager
async def _client_session():
    
    timeout = aiohttp.ClientTimeout(total=10)
    session = aiohttp.ClientSession(timeout=timeout)
    try:
        yield session
    finally:
        await session.close()
        logger.info("[ethereum] ClientSession closed")

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