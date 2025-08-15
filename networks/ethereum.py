import aiohttp
import asyncio
from datetime import datetime, timezone
from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input

USDT_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec7".lower()
ETHERSCAN_URL = "https://api.etherscan.io/api"

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

def _client_session():
    timeout = aiohttp.ClientTimeout(total=10)
    return aiohttp.ClientSession(timeout=timeout)

async def _get(session, params, retries=3):
    last_err = None
    for i in range(retries):
        try:
            async with session.get(ETHERSCAN_URL, params=params) as resp:
                if resp.status == 429:
                    await asyncio.sleep(0.7 * (i+1))
                    continue
                if resp.status >= 500:
                    await asyncio.sleep(0.5 * (i+1))
                    continue
                data = await resp.json()
                await asyncio.sleep(1)
                logger.info(f"[ethereum] ---_get----------------------------------------: {resp.status}")
                return data
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.5 * (i+1))
    raise RuntimeError(f"Etherscan request failed: {last_err}")

async def fetch_transaction(session, tx_hash: str) -> dict:
    params = {"module": "proxy", "action": "eth_getTransactionByHash", "txhash": tx_hash, "apikey": ETHERSCAN_API_KEY}
    data = await _get(session, params)
    tx_data = data.get("result")
    if not tx_data:
        return {"success": False, "status": "pending", "code": TxCode.NOT_FOUND, "error": "Транзакция не найдена"}
    return {"success": True, "data": tx_data}

async def check_in_block(tx_data) -> dict:
    block_number = tx_data.get("blockNumber")
    if not block_number:
        return {"success": False, "status": "pending", "code": TxCode.NOT_IN_BLOCK, "error": "Транзакция не включена в блок"}
    return {"success": True, "blockNumber": block_number}

async def check_timestamp_amount(session, tx_data) -> dict:
    try:
        decoded = decode_erc20_input(tx_data.get("input", "0x"))
    except Exception as e:
        logger.exception("[ethereum] decode error")
        return {"success": False, "status": "failed", "code": TxCode.DECODE_ERROR, "error": str(e)}

    if not decoded:
        return {"success": False, "status": "failed", "code": TxCode.DECODE_ERROR, "error": "Не удалось декодировать input"}

    amount = decoded["amount"] / 10**6  # USDT 6 decimals

    params_block = {"module": "proxy", "action": "eth_getBlockByNumber", "tag": tx_data["blockNumber"], "boolean": "true", "apikey": ETHERSCAN_API_KEY}
    block_response = await _get(session, params_block)
    block_data = block_response.get("result") or {}
    ts_hex = block_data.get("timestamp")
    if not ts_hex:
        return {"success": False, "status": "pending", "code": TxCode.API_ERROR, "error": "Нет timestamp блока"}

    ts_int = int(ts_hex, 16)
    timestamp = datetime.fromtimestamp(ts_int, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {"success": True, "amount": amount, "timestamp": timestamp}

async def check_is_erc20(tx_data) -> dict:
    if tx_data.get("to", "").lower() != USDT_CONTRACT:
        return {"success": False, "status": "failed", "code": TxCode.INVALID_TOKEN, "error": "Не USDT (ERC-20)"}
    return {"success": True}

async def check_recipient(tx_data, target_address: str) -> dict:
    decoded = decode_erc20_input(tx_data.get("input", "0x"))
    if not decoded:
        return {"success": False, "status": "failed", "code": TxCode.DECODE_ERROR, "error": "Не удалось декодировать input"}
    if decoded["to"].lower() != target_address.lower():
        return {"success": False, "status": "failed", "code": TxCode.INVALID_RECIPIENT, "error": f"Неправильный адрес. \nОтправлено на {decoded['to'].lower()}"}
    return {"success": True}

async def check_confirmations(session, block_number_hex: str) -> dict:
    if not block_number_hex:
        return {"success": False, "status": "pending", "code": TxCode.NOT_IN_BLOCK, "error": "Нет номера блока"}

    latest = await _get(session, {"module": "proxy", "action": "eth_blockNumber", "apikey": ETHERSCAN_API_KEY})
    latest_block_hex = latest.get("result")
    if not latest_block_hex:
        return {"success": False, "status": "pending", "code": TxCode.API_ERROR, "error": "Не удалось получить последний блок"}

    latest_block = int(latest_block_hex, 16)
    tx_block = int(block_number_hex, 16)
    confirmations = max(0, latest_block - tx_block)
    if confirmations >= ERC20_CONFIRMATIONS:
        return {"success": True, "confirmations": confirmations}
    return {"success": False, "status": "pending", "code": TxCode.LOW_CONFIRMATIONS, "confirmations": confirmations, "error": f"{confirmations}/{ERC20_CONFIRMATIONS}"}

async def check_transaction_stages(tx_hash: str, target_address: str, stage_set: set) -> dict:
    """
    Возвращает единый результат с нормализованными полями (см. TxCode).
    """
    stage_left = set(stage_set)
    try:
        async with _client_session() as session:
            tx_resp = await fetch_transaction(session, tx_hash)
            if not tx_resp["success"]:
                return _pending(tx_resp.get("code", TxCode.API_ERROR), list(stage_left), error=tx_resp.get("error"))

            tx = tx_resp["data"]

            if "in_block" in stage_left:
                r = await check_in_block(tx)
                logger.info(f"[ethereum] ---in_block--- result: {r}")
                if not r["success"]:
                    return _pending(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("in_block")

            if "is_erc20" in stage_left:
                r = await check_is_erc20(tx)
                logger.info(f"[ethereum] ---is_erc20--- result: {r}")
                if not r["success"]:
                    return _failed(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("is_erc20")

            if "recipient" in stage_left:
                r = await check_recipient(tx, target_address)
                logger.info(f"[ethereum] ---recipient--- result: {r}")
                if not r["success"]:
                    return _failed(r["code"], list(stage_left), error=r["error"])
                stage_left.discard("recipient")

            extra = {}
            if "transfer_params" in stage_left:
                r = await check_timestamp_amount(session, tx)
                logger.info(f"[ethereum] ---transfer_params--- result: {r}")
                if not r["success"]:
                    # тут это не «фатал», можно подождать (например, нет timestamp из-за лагов узла)
                    return _pending(r.get("code", TxCode.API_ERROR), list(stage_left), error=r.get("error"))
                extra.update({"timestamp": r["timestamp"], "amount": r["amount"]})
                stage_left.discard("transfer_params")

            if "confirmations" in stage_left:
                r = await check_confirmations(session, tx.get("blockNumber"))
                logger.info(f"[ethereum] ---confirmations--- result: {r}")
                if not r["success"]:
                    return _pending(r["code"], list(stage_left), error=r.get("error"), confirmations=r.get("confirmations", 0), **extra)
                extra.update({"confirmations": r["confirmations"]})
                stage_left.discard("confirmations")
            
            return {
                **_ok(stage=["completed"], **extra)
            }

    except Exception as e:
        logger.exception("[ethereum] internal error")
        return {"success": False, "status": "failed", "code": TxCode.INTERNAL_ERROR, "stage": list(stage_left), "error": str(e)}
