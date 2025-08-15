import json
import asyncio
import concurrent.futures
from threading import Thread
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo 

import redis
from celery_app import celery_app
from networks.ethereum import check_transaction_stages
from handlers.crypto import send_telegram_notification
from google_utils import save_transaction_hash, update_transaction_status
from config import logger

# --- Настройки ---
REDIS_HOST = "host.docker.internal"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_KEY_PREFIX = "tx:"
PENDING_TTL = 3 * 60 * 60                  # 3 часа TTL ключа
MAX_PENDING_DURATION = timedelta(minutes=2)  # в тексте так и было – 2 часа

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# async loop infra
_loop = None
_executor = None
_loop_thread = None

def get_or_create_event_loop():
    global _loop, _executor, _loop_thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        _loop_thread = Thread(target=run_loop, daemon=True)
        _loop_thread.start()
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    return _loop

def run_async_coroutine(coro, timeout=40):
    loop = get_or_create_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)

def _redis_key(tx_hash: str) -> str:
    return f"{REDIS_KEY_PREFIX}{tx_hash}"

def _touch_ttl(key: str):
    r.expire(key, PENDING_TTL)

def _store_initial(username, tx_hash, target_address):
    key = _redis_key(tx_hash)
    now = datetime.now(timezone.utc).isoformat()
    r.hset(key, mapping={
        "username": username,
        "target_address": target_address,
        "first_seen": now,
        "stage": "in_block,is_erc20,recipient,transfer_params,confirmations",
        "last_error_code": "",
        "last_error_text": ""
    })
    _touch_ttl(key)

def _update_stage(key: str, stage_left):
    r.hset(key, mapping={
        "stage": ",".join(stage_left)
    })
    _touch_ttl(key)

def _update_error(key: str, code: str, text: str):
    r.hset(key, mapping={
        "last_error_code": code or "",
        "last_error_text": text or ""
    })
    _touch_ttl(key)

def _parse_stage_list(s: str):
    return [x for x in (s or "").split(",") if x]



@celery_app.task
def check_erc20_confirmation_task(tx_hash, target_address, username):

    key = _redis_key(tx_hash)
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    now = datetime.now(kyiv_tz).strftime("%d.%m.%Y %H:%M:%S")

    stage_set = {"in_block", "is_erc20", "recipient", "transfer_params", "confirmations"}

    try:
        result = run_async_coroutine(check_transaction_stages(tx_hash, target_address, stage_set))
        code = result.get("code", "") != "low_confirmations"

        logger.info(f"[tasks] check_erc20 result: {result}")

        # сохраняем в Google сразу «как есть»
        google_params = [username, 
                         tx_hash, 
                         target_address, 
                         result.get("timestamp", "N/A"), 
                         now, 
                         result.get("status", "pending"), 
                         result.get("amount", "N/A"), 
                         result.get("error", "") if code else ''
                    ]

        save_transaction_hash(google_params)

        if result.get("success") and result.get("status") == "confirmed":
            google_update_params = {"status": [result.get("status"), 6]}
            msg = (
                f"✅ Ваша транзакция подтверждена!\n\n"
                f"💳 Хеш: `{tx_hash}`\n"
                f"Спасибо за использование нашего сервиса!"
            )
            run_async_coroutine(send_telegram_notification(username, msg))
            update_transaction_status(tx_hash, google_update_params)

            return
        else:
            if not r.exists(key):
                _store_initial(username, tx_hash, target_address)

        # not success → обновим стадии/ошибку и оставим ключ
        stage_left = result.get("stage", [])
        _update_stage(key, stage_left)
        _update_error(key, result.get("code", ""), result.get("error", ""))

        # для «фатальных» кейсов сразу уведомим
        code = result.get("code")
        if code in ("invalid_token", "invalid_recipient"):
            google_update_params = {"status": result.get("status")}
            if code == "invalid_token":
                msg = "❗️ Вы отправили токен, который не является USDT (ERC-20). Мы не можем обработать этот перевод."
            else:
                msg = "❗️ Ошибка: USDT были отправлены на адрес, отличающийся от выданного вам. Проверьте адрес назначения."
            google_update_params = {"status": [result.get("status"), 6], "error": [result.get("error",""), 8]}
            run_async_coroutine(send_telegram_notification(username, msg))
            update_transaction_status(tx_hash, google_update_params)
            r.delete(key)
        else:
            # pending — просто оставляем на periodic beat
            _touch_ttl(key)

    except Exception as e:
        logger.error(f"Ошибка проверки {tx_hash}: {e}")
        _update_error(key, "internal_error", str(e))


@celery_app.task
def periodic_check_pending_transactions():
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    now = datetime.now(kyiv_tz).strftime("%d.%m.%Y %H:%M:%S")
    """
    Периодический обход всех pending транзакций.
    """
    try:
        keys = r.keys(f"{REDIS_KEY_PREFIX}*")
        for key in keys:
            tx_data = r.hgetall(key)
            if not tx_data:
                continue

            tx_hash = key.split(":")[1]
            username = tx_data.get("username")
            target_address = tx_data.get("target_address")
            first_seen_str = tx_data.get("first_seen")
            stage_list = _parse_stage_list(tx_data.get("stage"))

            if not username or not target_address:
                logger.warning(f"[BEAT] Пропускаю {key} — нет username/target_address")
                r.delete(key)
                continue

            stage_set = set(stage_list) if stage_list else {"in_block","is_erc20","recipient","transfer_params","confirmations"}

            try:
                result = run_async_coroutine(check_transaction_stages(tx_hash, target_address, stage_set))
                logger.info(f"[BEAT] {tx_hash} result: {result}")

                if result.get("success"):
                    google_update_params = {"status": [result.get("status"), 6], "date_confirmation": [now, 5]}
                    msg = (
                        f"✅ Ваша транзакция подтверждена!\n\n"
                        f"💳 Хеш: `{tx_hash}`\n"
                        f"Спасибо за использование нашего сервиса!"
                    )
                    run_async_coroutine(send_telegram_notification(username, msg))
                    update_transaction_status(tx_hash, google_update_params)
                    r.delete(key)
                    continue

                # обновим стадии/ошибку
                _update_stage(key, result.get("stage", []))
                _update_error(key, result.get("code",""), result.get("error",""))

                code = result.get("code")

                # фатальные кейсы — сразу уведомление и чистим
                if code in ("invalid_token", "invalid_recipient"):
                    if code == "invalid_token":
                        msg = "❗️ Вы отправили токен, который не является USDT (ERC-20). Мы не можем обработать этот перевод."
                    else:
                        msg = "❗️ Ошибка: USDT были отправлены на адрес, отличающийся от выданного вам. Проверьте адрес назначения."
                    google_update_params = {"status": [result.get("status"), 6], "date_confirmation": [now, 5], "error": [result.get("error",""), 8]}
                    run_async_coroutine(send_telegram_notification(username, msg))
                    update_transaction_status(tx_hash, google_update_params)
                    r.delete(key)
                    continue

                # просрочка ожидания
                if first_seen_str:
                    first_seen = datetime.fromisoformat(first_seen_str)
                    if datetime.now(timezone.utc) - first_seen > MAX_PENDING_DURATION:
                        msg = (
                            "⚠️ Мы не получили подтверждения по вашей транзакции в течение 2 часов.\n\n"
                            "Она будет удалена. Если нужна помощь — напишите в поддержку."
                        )
                        error_msg = "Транзакция удалена: не получено подтверждение в течение 2 часов"
                        google_update_params = {"status": ["expired", 6], "date_confirmation": [now, 5], "error": [error_msg, 8]}
                        run_async_coroutine(send_telegram_notification(username, msg))
                        update_transaction_status(tx_hash, google_update_params)
                        r.delete(key)
                        continue

                # если просто pending — оставляем ключ с продлённым TTL
                _touch_ttl(key)

            except Exception as e:
                logger.error(f"[BEAT] Ошибка при проверке {tx_hash}: {e}")
                _update_error(key, "internal_error", str(e))
                _touch_ttl(key)

    except Exception as e:
        logger.error(f"[BEAT] Ошибка в periodic_check_pending_transactions: {e}")
