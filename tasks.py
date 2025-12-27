import asyncio
import concurrent.futures
from threading import Thread
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo 

from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage
from handlers.crypto import CryptoFSM
import redis
from redis.asyncio import Redis as AsyncRedis
from config import REDIS_DB_FSM, REDIS_DB, REDIS_KEY_PREFIX_ERC, REDIS_KEY_PREFIX_TRC, REDIS_URL
# Conditional import for Celery
try:
    from celery_app import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None

# Fallback decorator when Celery is not available
def celery_task_fallback(func):
    """Fallback decorator when Celery is not available"""
    if CELERY_AVAILABLE:
        return celery_app.task(func)
    else:
        # Return the function as-is when Celery is disabled
        return func

from networks.ethereum import check_transaction_stages
from networks.tron import check_tron_transaction, get_recent_transactions
from handlers.crypto import send_telegram_notification
from utils.backend_utils import update_transaction_status_async
from utils.api_client import get_api_client
from config import logger

# --- Настройки ---

PENDING_TTL = 3 * 60 * 60                  # 3 часа TTL ключа
MAX_PENDING_DURATION = timedelta(minutes=2)  # в тексте так и было – 2 часа

r = redis.Redis.from_url(REDIS_URL, db=REDIS_DB, decode_responses=True)

# --- Async Redis Singleton ---
r_async: AsyncRedis | None = None

def get_async_redis() -> AsyncRedis:
    global r_async
    if r_async is None:
        r_async = AsyncRedis.from_url(REDIS_URL, db=REDIS_DB_FSM)
    return r_async

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
    return f"{REDIS_KEY_PREFIX_ERC}{tx_hash}"

def _touch_ttl(key: str):
    if r:
        r.expire(key, PENDING_TTL)

def _store_initial(username, chat_id, bot_id, tx_hash, target_address, lang, amount, network):
    if not r:
        logger.error("Redis недоступен")
        return
    
    key = _redis_key(tx_hash)
    now = datetime.now(timezone.utc).isoformat()
    r.hset(key, mapping={
        "username": username,
        "chat_id": int(chat_id),
        "bot_id": int(bot_id),
        "target_address": target_address,
        "first_seen": now,
        "lang": lang,
        "stage": "in_block,is_erc20,recipient,transfer_params,confirmations",
        "last_error_code": "",
        "last_error_text": "",
        "amount": amount,
        "network": network
    })
    _touch_ttl(key)

def _update_stage(key: str, stage_left):
    if not r:
        return
    r.hset(key, mapping={
        "stage": ",".join(stage_left)
    })
    _touch_ttl(key)

def _update_error(key: str, code: str, text: str):
    if not r:
        return
    r.hset(key, mapping={
        "last_error_code": code or "",
        "last_error_text": text or ""
    })
    _touch_ttl(key)

def _parse_stage_list(s: str):
    return [x for x in (s or "").split(",") if x]

async def _advance_fsm_state(username: int, chat_id: int, bot_id: int, next_state, extra: dict | None = None):
    try:
        storage = RedisStorage(redis=AsyncRedis.from_url(REDIS_URL, db=REDIS_DB_FSM))
        logger.info(f"[tasks] _advanc1e_fsm_state storage: -------------------------------------------- {storage}")

        logger.info(f"[tasks] _advance_fsm_state params: {chat_id} ----- {username} ----- {bot_id}")
        key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=username)
        logger.info(f"[tasks] _advance_fsm_state key: {key}")

        if next_state is None:
            # очищаем FSM
            await storage.set_state(key, None)
            await storage.set_data(key, {})
            logger.info(f"[tasks] FSM состояние очищено для key: {key}")
            return

        await storage.set_state(key, next_state)
        current_state = await storage.get_state(key)
        logger.info(f"[tasks] _advance_fsm_state current_state after set: {current_state}")
        data = await storage.get_data(key) or {}
        logger.info(f"[tasks] _advance_fsm_state data: {data}")
        if extra:
            data.update(extra)
        await storage.set_data(key, data)
    except Exception as e:
        logger.error(f"Ошибка в _advance_fsm_state: {e}")

@celery_task_fallback
def check_confirmation_task(tx_hash, target_address, username, chat_id, bot_id, lang, network):
    if not r:
        logger.error("Redis недоступен для check_erc20_confirmation_task")
        return

    key = _redis_key(tx_hash)
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    now = datetime.now(kyiv_tz).strftime("%d.%m.%Y %H:%M:%S")



    try:
        if network == "ERC20":
            stage_set = {"in_block", "is_erc20", "recipient", "transfer_params", "confirmations"}          
            result = run_async_coroutine(check_transaction_stages(tx_hash, target_address, stage_set))
        elif network == "TRC20":
            result = run_async_coroutine(check_tron_transaction(tx_hash, target_address))
        
        amount = result.get("amount", "N/A")
        logger.info(f"[tasks] check_transaction result: {result}")

        # Для TRC20 и ERC20: записываем хеш сразу при обнаружении транзакции (даже если недостаточно подтверждений)
        if (network == "TRC20" or network == "ERC20") and result.get("success") is not False:
            # Получаем PIN-код по хешу транзакции из активных PIN-кодов
            pin_code = ""
            phone = ""
            from utils.backend_utils import get_active_pins
            active_pins = get_active_pins(network)
            
            # Ищем PIN-код по хешу транзакции
            for pin_data in active_pins:
                if pin_data.get("tx_hash") == tx_hash:
                    pin_code = pin_data.get("pin_code", "")
                    phone = pin_data.get("phone", "")
                    break
            
            # Транзакция найдена, записываем хеш сразу
            google_params = [username, 
                             tx_hash, 
                             target_address, 
                             result.get("timestamp", "N/A"), 
                             now, 
                             result.get("status", "pending"), 
                             amount, 
                             result.get("error", ""),
                             phone  # Добавляем номер телефона
                        ]
            
            # Сохраняем хеш в БД через API (без Google Sheets)
            try:
                from utils.backend_utils import save_transaction_hash_async
                # Получаем PIN-код для связи
                pin_code = ""
                for pin_data in active_pins:
                    if pin_data.get("tx_hash") == tx_hash:
                        pin_code = pin_data.get("pin_code", "")
                        break
                
                # Сохраняем в БД (используем run_async_coroutine для синхронного контекста)
                run_async_coroutine(save_transaction_hash_async(
                    username=username,
                    tx_hash=tx_hash,
                    target_address=target_address,
                    timestamp=result.get("timestamp", "N/A"),
                    now=now,
                    status=result.get("status", "pending"),
                    amount=float(amount) if isinstance(amount, (int, float)) else 0.0,
                    phone=phone,
                    network=network,
                    pin_code=pin_code
                ))
                logger.info(f"[tasks] {network} хеш {tx_hash} записан в БД")
            except Exception as e:
                logger.error(f"[tasks] Ошибка при сохранении хеша {tx_hash} в БД: {e}", exc_info=True)

        if result.get("success") and result.get("status") == "confirmed":
            # Обновляем статус в БД
            run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
            
            msg = {
                "msg_status": "tx_confirmed",
                "lang": lang,
                "amount_result": amount,
                "target_address": target_address,
                "timestamp": result.get("timestamp", "N/A"),
            }
            
            run_async_coroutine(_advance_fsm_state(
                username=username,
                chat_id=chat_id,
                bot_id=bot_id,
                next_state=CryptoFSM.contact,
                extra={
                    "amount_result": amount,
                    "tx_hash": tx_hash,
                    "target_address": target_address,
                    "timestamp": result.get("timestamp", "N/A"),
                },
            ))
            run_async_coroutine(send_telegram_notification(chat_id, msg))
            return
        else:
            if not r.exists(key):
                _store_initial(username, chat_id, bot_id, tx_hash, target_address, lang, amount, network)

        # not success → обновим стадии/ошибку и оставим ключ
        if network == "ERC20":
            stage_left = result.get("stage", [])
            _update_stage(key, stage_left)
            _update_error(key, result.get("code", ""), result.get("error", ""))

        # для «фатальных» кейсов сразу уведомим
        code = result.get("code")
        if code in ("invalid_token", "invalid_recipient"):
            google_update_params = {"status": result.get("status")}
            msg = {                
                "lang": lang,
                "amount_result": amount,
                "target_address": target_address,
                "timestamp": result.get("timestamp", "N/A"),
            }
            if code == "invalid_token":
                msg.update({"msg_status": "invalid_token_erc"})
            else:
                msg.update({"msg_status": "invalid_recipient"})
                
            # Обновляем статус в БД
            run_async_coroutine(update_transaction_status_async(tx_hash, "failed", network))
            run_async_coroutine(send_telegram_notification(chat_id, msg))
            run_async_coroutine(_advance_fsm_state(username, chat_id, bot_id, None))
            
            r.delete(key)
        else:
            # pending — просто оставляем на periodic beat
            _touch_ttl(key)

    except Exception as e:
        logger.error(f"Ошибка проверки {tx_hash}: {e}")
        if r:
            _update_error(key, "internal_error", str(e))

@celery_task_fallback
def periodic_check_pending_transactions():
    if not r:
        logger.error("Redis недоступен для periodic_check_pending_transactions")
        return
        
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    now = datetime.now(kyiv_tz).strftime("%d.%m.%Y %H:%M:%S")
    
    """
    Периодический обход всех pending транзакций.
    """
    try:
        # keys = r.keys(f"{REDIS_KEY_PREFIX_ERC}*")
        patterns = [f"{REDIS_KEY_PREFIX_ERC}*", f"{REDIS_KEY_PREFIX_TRC}*"]

        for pattern in patterns:
            for key in r.scan_iter(match=pattern):
                tx_data = r.hgetall(key)
                if not tx_data:
                    continue

                tx_hash = key.split(":")[1]
                username = tx_data.get("username")
                lang = tx_data.get("lang")
                chat_id = tx_data.get("chat_id")
                bot_id = tx_data.get("bot_id")
                target_address = tx_data.get("target_address")
                first_seen_str = tx_data.get("first_seen")
                amount = tx_data.get("amount", "N/A")
                network = tx_data.get("network", "N/A")

                if not username or not target_address:
                    logger.warning(f"[BEAT] Пропускаю {key} — нет username/target_address")
                    r.delete(key)
                    continue

                

                try:
                    if network == "ERC20":
                        stage_list = _parse_stage_list(tx_data.get("stage"))
                        stage_set = set(stage_list) if stage_list else {"in_block","is_erc20","recipient","transfer_params","confirmations"}
                        result = run_async_coroutine(check_transaction_stages(tx_hash, target_address, stage_set))
                    if network == "TRC20":
                        result = run_async_coroutine(check_tron_transaction(tx_hash, target_address))
                    # result = run_async_coroutine(check_transaction_stages(tx_hash, target_address, stage_set))
                    logger.info(f"[BEAT] {tx_hash} result: {result}")

                    if result.get("success") and result.get("status") == "confirmed":
                        # Обновляем статус в БД
                        run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
                        
                        msg = {
                            "msg_status": "tx_confirmed",
                            "lang": lang,
                            "amount_result": amount,
                            "target_address": target_address,
                            "timestamp": result.get("timestamp", "N/A"),
                        }
                        run_async_coroutine(send_telegram_notification(chat_id, msg))
                        run_async_coroutine(_advance_fsm_state(
                            username=username,
                            chat_id=chat_id,
                            bot_id=bot_id,
                            next_state=CryptoFSM.contact,
                            extra={
                                "amount_result": amount,
                                "tx_hash": tx_hash,
                                "target_address": target_address,
                                "timestamp": result.get("timestamp", "N/A"),
                            },
                        ))
                        r.delete(key)
                        continue

                    # обновим стадии/ошибку
                    if network == "ERC20":
                        _update_stage(key, result.get("stage", []))
                        _update_error(key, result.get("code",""), result.get("error",""))

                    code = result.get("code")

                    # фатальные кейсы — сразу уведомление и чистим
                    if code in ("invalid_token", "invalid_recipient"):
                        msg = {                
                            "lang": lang,
                            "amount_result": amount,
                            "target_address": target_address,
                            "timestamp": result.get("timestamp", "N/A"),
                        }
                        if code == "invalid_token":
                            if network == "ERC20":
                                msg.update({"msg_status": "invalid_token_erc"})
                            if network == "TRC20":
                                msg.update({"msg_status": "invalid_token_trc"})
                            
                        else:
                            msg.update({"msg_status": "invalid_recipient"})
                        
                        # Обновляем статус в БД
                        run_async_coroutine(update_transaction_status_async(tx_hash, "failed", network))
                        run_async_coroutine(send_telegram_notification(chat_id, msg))
                        run_async_coroutine(_advance_fsm_state(username, chat_id, bot_id, None))

                        r.delete(key)
                        continue

                    # просрочка ожидания
                    if first_seen_str:
                        first_seen = datetime.fromisoformat(first_seen_str)
                        if datetime.now(timezone.utc) - first_seen > MAX_PENDING_DURATION:
                            msg = {     
                                "msg_status": "expired",           
                                "lang": lang,
                                "amount_result": amount,
                                "target_address": target_address,
                                "timestamp": result.get("timestamp", "N/A"),
                            }
                            error_msg = f"Транзакция удалена: не получено подтверждение в течение 2 часов\n{result.get('error','')}"
                            # Обновляем статус в БД
                            run_async_coroutine(update_transaction_status_async(tx_hash, "failed", network))
                            run_async_coroutine(send_telegram_notification(chat_id, msg))
                            run_async_coroutine(_advance_fsm_state(username, chat_id, bot_id, None))

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


# =============================================================================
# НОВАЯ ЗАДАЧА ДЛЯ ПРОВЕРКИ PENDING ТРАНЗАКЦИЙ ИЗ БАЗЫ ДАННЫХ
# =============================================================================

@celery_task_fallback
def periodic_check_db_pending_transactions():
    """
    Периодически проверяет все pending транзакции из базы данных
    и обновляет их статус на основе проверки в блокчейне
    """
    try:
        from utils.api_client import get_api_client
        
        logger.info("[DB_CHECK] Начинаем проверку pending транзакций из базы данных")
        
        api_client = get_api_client()
        
        # Получаем все pending транзакции из базы данных
        async def get_pending_transactions():
            try:
                result = await api_client._request(
                    "GET", 
                    "/transactions/", 
                    params={
                        "status": "pending",
                        "limit": 100
                    }
                )
                return result.get("items", [])
            except Exception as e:
                logger.error(f"[DB_CHECK] Ошибка получения pending транзакций: {e}")
                return []
        
        pending_transactions = run_async_coroutine(get_pending_transactions())
        
        if not pending_transactions:
            logger.info("[DB_CHECK] Нет pending транзакций для проверки")
            return
        
        logger.info(f"[DB_CHECK] Найдено {len(pending_transactions)} pending транзакций")
        
        for tx in pending_transactions:
            tx_hash = tx.get("hash")
            tx_id = tx.get("id")
            table_type = tx.get("table_type", "TRC")
            to_address = tx.get("to_address")
            amount = tx.get("amount")
            created_at = tx.get("created_at")
            
            # Если нет хеша, но есть to_address и сумма, пытаемся найти транзакцию по адресу
            if not tx_hash:
                if not to_address or not amount:
                    logger.warning(f"[DB_CHECK] Пропускаем транзакцию {tx_id}: нет hash, to_address или amount")
                    continue
                
                # Пытаемся найти транзакцию по адресу получателя и сумме
                logger.info(f"[DB_CHECK] Транзакция {tx_id} без хеша, ищем по адресу {to_address} и сумме {amount}")
                
                # Определяем сеть
                network = "ERC20" if table_type == "ERC" else "TRC20"
                
                try:
                    # Для TRC20: получаем последние транзакции на адресе
                    if network == "TRC20":
                        import aiohttp
                        
                        async def find_transaction_by_address():
                            async with aiohttp.ClientSession() as session:
                                logger.info(f"[DB_CHECK] 🔍 Поиск транзакции TRC20: адрес={to_address[:8]}...{to_address[-6:]}, сумма={amount} USDT")
                                recent_txs_response = await get_recent_transactions(session, to_address, limit=50)
                                if recent_txs_response.get("success"):
                                    transactions_data = recent_txs_response.get("data", {})
                                    transactions = transactions_data.get("data", [])
                                    
                                    logger.info(f"[DB_CHECK] 📊 Получено {len(transactions)} транзакций для проверки")
                                    
                                    if transactions:
                                        # Ищем транзакцию с похожей суммой (с учетом погрешности)
                                        target_amount = float(amount)
                                        tolerance = 0.01  # 1% погрешность
                                        
                                        logger.info(f"[DB_CHECK] 🔎 Ищем транзакцию с суммой {target_amount} USDT (±{tolerance*100}%)")
                                        
                                        for idx, recent_tx in enumerate(transactions):
                                            # Получаем сумму из транзакции
                                            value = recent_tx.get("value", 0)
                                            decimals = recent_tx.get("token_info", {}).get("decimals", 6)
                                            tx_amount = value / (10 ** decimals) if value else 0
                                            
                                            # Логируем первые несколько транзакций для отладки
                                            if idx < 3:
                                                logger.debug(f"[DB_CHECK] Транзакция #{idx+1}: сумма={tx_amount} USDT, hash={recent_tx.get('transaction_id', 'N/A')[:16]}...")
                                            
                                            if abs(tx_amount - target_amount) <= (target_amount * tolerance):
                                                # Нашли транзакцию! Обновляем хеш и проверяем статус
                                                found_hash = recent_tx.get("transaction_id") or recent_tx.get("hash")
                                                if found_hash:
                                                    logger.info(f"[DB_CHECK] ✅ Найдена транзакция {found_hash} для записи {tx_id} (сумма: {tx_amount} USDT, ожидалось: {target_amount} USDT)")
                                                    
                                                    # Обновляем хеш в базе данных
                                                    await api_client.update_transaction(
                                                        transaction_id=tx_id,
                                                        hash=found_hash
                                                    )
                                                    logger.info(f"[DB_CHECK] ✅ Хеш {found_hash} обновлен для транзакции {tx_id}")
                                                    
                                                    # Теперь проверяем статус транзакции
                                                    logger.info(f"[DB_CHECK] 🔍 Проверяем статус транзакции {found_hash} в блокчейне")
                                                    result = await check_tron_transaction(found_hash, to_address)
                                                    
                                                    if result.get("success") and result.get("status") == "confirmed":
                                                        logger.info(f"[DB_CHECK] ✅ Транзакция {found_hash} подтверждена, обновляем статус на 'completed'")
                                                        await update_transaction_status_async(found_hash, "completed", network)
                                                    elif result.get("status") == "failed":
                                                        code = result.get("code")
                                                        # НЕ помечаем как failed если это invalid_recipient - транзакция успешна на блокчейне
                                                        if code in ("invalid_token", "contract_error", "no_transfers"):
                                                            logger.info(f"[DB_CHECK] ❌ Транзакция {found_hash} провалилась ({code}), обновляем статус на 'failed'")
                                                            await update_transaction_status_async(found_hash, "failed", network)
                                                        elif code == "invalid_recipient":
                                                            # Транзакция успешна на блокчейне, но адрес не совпадает - помечаем как completed
                                                            logger.warning(f"[DB_CHECK] ⚠️ Транзакция {found_hash} успешна на блокчейне, но адрес получателя не совпадает. Помечаем как completed.")
                                                            await update_transaction_status_async(found_hash, "completed", network)
                                                    
                                                    return
                                        
                                        logger.warning(f"[DB_CHECK] ❌ Транзакция с суммой {amount} USDT не найдена на адресе {to_address[:8]}...{to_address[-6:]} (проверено {len(transactions)} транзакций)")
                                    else:
                                        logger.warning(f"[DB_CHECK] ⚠️ Нет транзакций для адреса {to_address[:8]}...{to_address[-6:]}")
                                else:
                                    error_msg = recent_txs_response.get('error', 'Unknown error')
                                    logger.error(f"[DB_CHECK] ❌ Не удалось получить транзакции для адреса {to_address[:8]}...{to_address[-6:]}: {error_msg}")
                        
                        run_async_coroutine(find_transaction_by_address())
                    elif network == "ERC20":
                        # Для ERC20: получаем последние транзакции на адресе
                        from networks.ethereum import get_recent_erc20_transactions, check_transaction_stages, get_client_session
                        import aiohttp
                        
                        async def find_erc20_transaction_by_address():
                            session = await get_client_session()
                            try:
                                recent_txs_response = await get_recent_erc20_transactions(session, to_address, limit=50)
                                if recent_txs_response.get("success"):
                                    transactions = recent_txs_response.get("data", [])
                                    
                                    if transactions:
                                        # Ищем транзакцию с похожей суммой (с учетом погрешности)
                                        target_amount = float(amount)
                                        tolerance = 0.01  # 1% погрешность
                                        
                                        for recent_tx in transactions:
                                            # Получаем сумму из транзакции (Etherscan API формат)
                                            # Etherscan возвращает value как строку в wei
                                            value_str = recent_tx.get("value", "0")
                                            decimals = int(recent_tx.get("tokenDecimal", 6))
                                            
                                            try:
                                                # Преобразуем hex или строку в int
                                                if isinstance(value_str, str) and value_str.startswith("0x"):
                                                    value = int(value_str, 16)
                                                else:
                                                    value = int(value_str) if value_str else 0
                                                
                                                tx_amount = value / (10 ** decimals) if value else 0
                                            except (ValueError, TypeError):
                                                logger.warning(f"[DB_CHECK] Не удалось распарсить сумму транзакции: {value_str}")
                                                continue
                                            
                                            # Проверяем адрес получателя (должен совпадать с to_address)
                                            tx_to = recent_tx.get("to", "").lower()
                                            target_to = to_address.lower()
                                            
                                            if tx_to == target_to and abs(tx_amount - target_amount) <= (target_amount * tolerance):
                                                # Нашли транзакцию! Обновляем хеш и проверяем статус
                                                found_hash = recent_tx.get("hash")
                                                if found_hash:
                                                    logger.info(f"[DB_CHECK] Найдена ERC20 транзакция {found_hash} для записи {tx_id} (сумма: {tx_amount})")
                                                    
                                                    # Обновляем хеш в базе данных
                                                    await api_client.update_transaction(
                                                        transaction_id=tx_id,
                                                        hash=found_hash
                                                    )
                                                    
                                                    # Теперь проверяем статус транзакции
                                                    stage_set = {"in_block", "is_erc20", "recipient", "transfer_params", "confirmations"}
                                                    result = await check_transaction_stages(found_hash, to_address, stage_set)
                                                    
                                                    if result.get("success") and result.get("status") == "confirmed":
                                                        logger.info(f"[DB_CHECK] Транзакция {found_hash} подтверждена, обновляем статус на 'completed'")
                                                        await update_transaction_status_async(found_hash, "completed", network)
                                                    elif result.get("status") == "failed":
                                                        code = result.get("code")
                                                        # НЕ помечаем как failed если это invalid_recipient - транзакция успешна на блокчейне
                                                        if code in ("invalid_token", "contract_error", "no_transfers"):
                                                            logger.info(f"[DB_CHECK] Транзакция {found_hash} провалилась ({code}), обновляем статус на 'failed'")
                                                            await update_transaction_status_async(found_hash, "failed", network)
                                                        elif code == "invalid_recipient":
                                                            # Транзакция успешна на блокчейне, но адрес не совпадает - помечаем как completed
                                                            logger.warning(f"[DB_CHECK] Транзакция {found_hash} успешна на блокчейне, но адрес получателя не совпадает. Помечаем как completed.")
                                                            await update_transaction_status_async(found_hash, "completed", network)
                                                    
                                                    return
                                        
                                        logger.info(f"[DB_CHECK] Транзакция с суммой {amount} не найдена на адресе {to_address}")
                                    else:
                                        logger.warning(f"[DB_CHECK] Нет транзакций для адреса {to_address}")
                                else:
                                    logger.warning(f"[DB_CHECK] Не удалось получить транзакции для адреса {to_address}: {recent_txs_response.get('error', 'Unknown error')}")
                            finally:
                                await session.close()
                        
                        run_async_coroutine(find_erc20_transaction_by_address())
                    else:
                        logger.warning(f"[DB_CHECK] Поиск транзакций по адресу для {network} пока не реализован")
                    
                except Exception as e:
                    logger.error(f"[DB_CHECK] Ошибка поиска транзакции по адресу для {tx_id}: {e}")
                
                continue
            
            # Определяем сеть
            network = "ERC20" if table_type == "ERC" else "TRC20"
            
            logger.info(f"[DB_CHECK] Проверяем транзакцию {tx_hash} ({network})")
            logger.info(f"[DB_CHECK] to_address из БД: {to_address}")
            
            try:
                # Проверяем статус в блокчейне
                # Если нет to_address, проверяем транзакцию без проверки адреса получателя
                if network == "ERC20":
                    stage_set = {"in_block", "is_erc20", "recipient", "transfer_params", "confirmations"}
                    if to_address:
                        result = run_async_coroutine(check_transaction_stages(tx_hash, to_address, stage_set))
                    else:
                        # Если нет to_address, проверяем только базовые параметры
                        logger.warning(f"[DB_CHECK] Нет to_address для транзакции {tx_hash}, проверяем только базовый статус")
                        # Используем упрощенную проверку без проверки адреса
                        from networks.ethereum import check_transaction_stages
                        # Проверяем без проверки получателя
                        stage_set_no_recipient = {"in_block", "is_erc20", "transfer_params", "confirmations"}
                        result = run_async_coroutine(check_transaction_stages(tx_hash, "", stage_set_no_recipient))
                else:  # TRC20
                    if to_address:
                        logger.info(f"[DB_CHECK] Проверяем TRC20 транзакцию {tx_hash} с адресом получателя из БД: {to_address}")
                        result = run_async_coroutine(check_tron_transaction(tx_hash, to_address))
                    else:
                        # Если нет to_address, проверяем транзакцию без проверки адреса получателя
                        logger.warning(f"[DB_CHECK] Нет to_address для транзакции {tx_hash}, проверяем только базовый статус")
                        # Используем упрощенную проверку - проверяем только что транзакция успешна на блокчейне
                        from networks.tron import fetch_transaction, check_confirmations, _client_session
                        import asyncio
                        
                        async def check_tx_without_address():
                            async with _client_session() as session:
                                tx_resp = await fetch_transaction(session, tx_hash)
                                if not tx_resp.get("success"):
                                    return tx_resp
                                
                                data = tx_resp["data"]
                                # Проверяем только что транзакция успешна и подтверждена
                                contract_ret = data.get("contractRet") or data.get("contract_ret") or data.get("result")
                                confirmed = data.get("confirmed", True)
                                block_number = data.get("blockNumber") or data.get("block")
                                
                                # Если транзакция успешна и подтверждена, проверяем подтверждения
                                if (contract_ret == "SUCCESS" or (confirmed and block_number)):
                                    conf_resp = await check_confirmations(session, data)
                                    if conf_resp.get("success"):
                                        # Транзакция успешна на блокчейне
                                        from networks.tron import _ok
                                        return _ok(
                                            stage=["completed"],
                                            amount=0,  # Не знаем сумму без проверки трансфера
                                            from_address="",
                                            to_address="",
                                            timestamp="",
                                            confirmations=conf_resp.get("confirmations", 0)
                                        )
                                    else:
                                        from networks.tron import _pending
                                        return _pending(
                                            conf_resp.get("code", "low_confirmations"),
                                            stage=["confirmations"],
                                            error=conf_resp.get("error", "")
                                        )
                                else:
                                    from networks.tron import _failed
                                    return _failed(
                                        "contract_error",
                                        error=f"Транзакция не успешна: contractRet={contract_ret}, confirmed={confirmed}"
                                    )
                        
                        result = run_async_coroutine(check_tx_without_address())
                
                logger.info(f"[DB_CHECK] Результат проверки {tx_hash}: {result.get('status')}, success={result.get('success')}, code={result.get('code')}, confirmations={result.get('confirmations', 0)}")
                
                # Если транзакция подтверждена на блокчейне, обновляем статус на completed
                # НЕ проверяем адрес получателя, так как транзакция уже успешна на блокчейне
                if result.get("success") and result.get("status") == "confirmed":
                    logger.info(f"[DB_CHECK] Транзакция {tx_hash} подтверждена на блокчейне, обновляем статус на 'completed'")
                    run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
                
                # Если статус pending, но транзакция успешна на блокчейне (есть confirmations или код low_confirmations)
                # и прошло достаточно времени (транзакция старая), помечаем как completed
                elif result.get("status") == "pending":
                    code = result.get("code")
                    confirmations = result.get("confirmations", 0)
                    
                    # Если это low_confirmations, но транзакция успешна на блокчейне и прошло время
                    # (например, больше 1 часа с момента создания), считаем её подтвержденной
                    if code == "low_confirmations" and confirmations > 0:
                        # Проверяем время создания транзакции
                        if created_at:
                            try:
                                from datetime import datetime, timezone
                                if isinstance(created_at, str):
                                    # Парсим строку даты
                                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                else:
                                    created_dt = created_at
                                
                                time_diff = datetime.now(timezone.utc) - created_dt.replace(tzinfo=timezone.utc) if created_dt.tzinfo is None else created_dt
                                
                                # Если прошло больше 1 часа, считаем транзакцию подтвержденной
                                if time_diff.total_seconds() > 3600:
                                    logger.info(f"[DB_CHECK] Транзакция {tx_hash} успешна на блокчейне, прошло {time_diff.total_seconds()/3600:.1f} часов, обновляем статус на 'completed'")
                                    run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
                                else:
                                    logger.info(f"[DB_CHECK] Транзакция {tx_hash} все еще pending (confirmations={confirmations}, прошло {time_diff.total_seconds()/60:.1f} минут)")
                            except Exception as e:
                                logger.warning(f"[DB_CHECK] Ошибка при проверке времени транзакции {tx_hash}: {e}")
                        else:
                            # Если нет времени создания, но есть подтверждения, считаем подтвержденной
                            if confirmations >= 12:
                                logger.info(f"[DB_CHECK] Транзакция {tx_hash} успешна на блокчейне с {confirmations} подтверждениями, обновляем статус на 'completed'")
                                run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
                            else:
                                logger.info(f"[DB_CHECK] Транзакция {tx_hash} все еще pending (confirmations={confirmations})")
                    else:
                        logger.info(f"[DB_CHECK] Транзакция {tx_hash} все еще pending (status={result.get('status')}, code={code})")
                    
                # Если транзакция провалилась (фатальные ошибки) - только если это реальная ошибка контракта
                elif result.get("status") == "failed":
                    code = result.get("code")
                    # НЕ помечаем как failed если это invalid_recipient - это может быть другая транзакция
                    # Помечаем как failed только реальные ошибки контракта
                    if code in ("invalid_token", "contract_error", "no_transfers"):
                        logger.info(f"[DB_CHECK] Транзакция {tx_hash} провалилась ({code}), обновляем статус на 'failed'")
                        run_async_coroutine(update_transaction_status_async(tx_hash, "failed", network))
                    elif code == "invalid_recipient":
                        # Если адрес получателя не совпадает, но транзакция успешна на блокчейне,
                        # это может быть другая транзакция - не помечаем как failed
                        logger.warning(f"[DB_CHECK] Транзакция {tx_hash} успешна на блокчейне, но адрес получателя не совпадает. Возможно, это другая транзакция.")
                        # Оставляем статус как есть или помечаем как completed, если транзакция успешна
                        # Проверяем, есть ли подтверждения
                        if result.get("confirmations", 0) >= 12:
                            logger.info(f"[DB_CHECK] Транзакция {tx_hash} успешна на блокчейне с достаточными подтверждениями, обновляем статус на 'completed'")
                            run_async_coroutine(update_transaction_status_async(tx_hash, "completed", network))
                    
            except Exception as e:
                logger.error(f"[DB_CHECK] Ошибка проверки транзакции {tx_hash}: {e}", exc_info=True)
        
        logger.info("[DB_CHECK] Проверка pending транзакций завершена")
        
    except Exception as e:
        logger.error(f"[DB_CHECK] Критическая ошибка в periodic_check_db_pending_transactions: {e}")


# =============================================================================
# НОВАЯ ЗАДАЧА ДЛЯ МОНИТОРИНГА PIN-КОДОВ
# =============================================================================

@celery_task_fallback
def monitor_active_pins():
    """
    Мониторит активные PIN-коды и проверяет соответствующие транзакции
    """
    try:
        from utils.backend_utils import get_active_pins, mark_pin_used_async
        from utils.api_client import get_api_client
        from networks.tron import monitor_wallet_for_new_transactions, _client_session as tron_client_session
        from networks.ethereum import monitor_erc20_wallet_for_new_transactions, get_client_session as get_eth_session
        from handlers.crypto import send_telegram_notification
        
        logger.info("[PIN_MONITOR] Начинаем мониторинг активных PIN-кодов")
        
        # Очищаем истекшие PIN-коды для обеих сетей
        from utils.backend_utils import cleanup_expired_pins
        trc_cleaned = cleanup_expired_pins("TRC20")
        erc_cleaned = cleanup_expired_pins("ERC20")
        total_cleaned = trc_cleaned + erc_cleaned
        
        if total_cleaned > 0:
            logger.info(f"[PIN_MONITOR] Очищено {total_cleaned} истекших PIN-кодов (TRC20: {trc_cleaned}, ERC20: {erc_cleaned})")
        
        # Получаем активные PIN-коды для каждой сети отдельно
        all_active_pins = []
        
        # Получаем PIN-коды для TRC20
        trc_pins = get_active_pins("TRC20")
        if trc_pins:
            all_active_pins.extend(trc_pins)
            logger.info(f"[PIN_MONITOR] Найдено {len(trc_pins)} активных TRC20 PIN-кодов")
        
        # Получаем PIN-коды для ERC20
        erc_pins = get_active_pins("ERC20")
        if erc_pins:
            all_active_pins.extend(erc_pins)
            logger.info(f"[PIN_MONITOR] Найдено {len(erc_pins)} активных ERC20 PIN-кодов")
        
        if not all_active_pins:
            logger.info("[PIN_MONITOR] Нет активных PIN-кодов для мониторинга")
            return
        
        logger.info(f"[PIN_MONITOR] Всего найдено {len(all_active_pins)} активных PIN-кодов")
        for pin in all_active_pins:
            logger.info(f"[PIN_MONITOR] PIN: {pin.get('pin_code')}, Amount: {pin.get('amount')}, Target: {pin.get('target_wallet')}, Network: {pin.get('network')}")
        
        # Группируем PIN-коды по сетям и адресам
        pins_by_network = {}
        for pin_data in all_active_pins:
            network = pin_data.get('network', 'TRC20')
            target_wallet = pin_data.get('target_wallet')
            
            if not target_wallet:
                continue
            
            if network not in pins_by_network:
                pins_by_network[network] = {}
            
            if target_wallet not in pins_by_network[network]:
                pins_by_network[network][target_wallet] = []
            
            pins_by_network[network][target_wallet].append(pin_data)
        
        # Мониторим каждый адрес
        for network, wallets in pins_by_network.items():
            for wallet_address, pins in wallets.items():
                try:
                    logger.info(
                        f"[PIN_MONITOR] Начало мониторинга. Network={network}, Wallet={wallet_address}, PIN_count={len(pins)}"
                    )
                    
                    # Для TRC20 используем TronScan API
                    if network == "TRC20":
                        logger.info(f"[PIN_MONITOR] TRC20 monitor call → wallet={wallet_address}")
                        # Получаем сессию и запускаем мониторинг
                        async def monitor_with_session():
                            async with tron_client_session() as session:
                                return await monitor_wallet_for_new_transactions(
                                    session=session,
                                    wallet_address=wallet_address,
                                    active_pins=pins
                                )
                        result = run_async_coroutine(monitor_with_session())
                        
                        if result.get("success"):
                            matched_transactions = result.get("matched_transactions", [])
                            
                            for match in matched_transactions:
                                tx_hash = match["tx_hash"]
                                pin_data = match["pin_data"]
                                transaction_data = match["transaction_data"]
                                
                                pin_code = pin_data.get("pin_code")
                                user_id = pin_data.get("user_id")
                                
                                logger.info(f"[PIN_MONITOR] Найдена соответствующая транзакция: {tx_hash} для PIN {pin_code}")
                                
                                # Записываем хеш сразу при обнаружении транзакции
                                run_async_coroutine(mark_pin_used_async(pin_code, tx_hash, network))
                                
                                # Определяем статус транзакции
                                tx_status = transaction_data.get("status", "pending")
                                
                                if tx_status == "confirmed":
                                    # Транзакция полностью подтверждена
                                    msg = {
                                        "msg_status": "tx_confirmed",
                                        "lang": "ru",
                                        "amount_result": transaction_data.get("amount", "N/A"),
                                        "target_address": wallet_address,
                                        "timestamp": transaction_data.get("timestamp", "N/A"),
                                    }
                                    
                                    chat_id = pin_data.get("chat_id")
                                    if chat_id:
                                        run_async_coroutine(send_telegram_notification(chat_id, msg))
                                    
                                    logger.info(f"[PIN_MONITOR] Транзакция {tx_hash} подтверждена для PIN {pin_code}")
                                else:
                                    # Транзакция найдена, но еще не подтверждена
                                    logger.info(f"[PIN_MONITOR] Транзакция {tx_hash} найдена для PIN {pin_code}, статус: {tx_status}")
                        
                        else:
                            logger.warning(f"[PIN_MONITOR] Ошибка мониторинга {wallet_address}: {result.get('error')}")
                    
                    # Для ERC20 используем Etherscan API
                    elif network == "ERC20":
                        logger.info(f"[PIN_MONITOR] ERC20 monitor call → wallet={wallet_address}")
                        async def monitor_with_session_eth():
                            session = await get_eth_session()
                            try:
                                return await monitor_erc20_wallet_for_new_transactions(
                                    session=session,
                                    wallet_address=wallet_address,
                                    active_pins=pins
                                )
                            finally:
                                await session.close()

                        result = run_async_coroutine(monitor_with_session_eth())

                        if result.get("success"):
                            matched_transactions = result.get("matched_transactions", [])
                            logger.info(f"[PIN_MONITOR] ERC20 результат мониторинга: success, найдено совпадений: {len(matched_transactions)} для {wallet_address}")
                            for match in matched_transactions:
                                tx_hash = match["tx_hash"]
                                pin_data = match["pin_data"]
                                transaction_data = match["transaction_data"]

                                pin_code = pin_data.get("pin_code")
                                user_id = pin_data.get("user_id")

                                logger.info(
                                    f"[PIN_MONITOR] ERC20 match: tx_hash={tx_hash}, pin={pin_code}, user_id={user_id}, "
                                    f"amount={transaction_data.get('amount')}, status={transaction_data.get('status')}, "
                                    f"to={transaction_data.get('to_address')}, from={transaction_data.get('from_address')}"
                                )

                                # Записываем хеш: обновляем транзакцию в БД
                                logger.info(f"[PIN_MONITOR] ERC20 пытаемся пометить PIN={pin_code} как used и записать hash")
                                used_ok = run_async_coroutine(mark_pin_used_async(pin_code, tx_hash, network))
                                logger.info(f"[PIN_MONITOR] ERC20 mark_pin_used_async result: {used_ok}")
                                
                                # Если не удалось обновить по PIN, создаем новую транзакцию
                                if not used_ok:
                                    try:
                                        from utils.backend_utils import save_transaction_hash_async
                                        run_async_coroutine(save_transaction_hash_async(
                                            username=pin_data.get("user_id", 0),
                                            tx_hash=tx_hash,
                                            target_address=wallet_address,
                                            timestamp=transaction_data.get("timestamp", "N/A"),
                                            now=datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M:%S"),
                                            status=transaction_data.get("status", "pending"),
                                            amount=float(transaction_data.get("amount", 0)),
                                            phone=pin_data.get("phone", ""),
                                            network=network,
                                            pin_code=pin_code
                                        ))
                                        logger.info(f"[PIN_MONITOR] ERC20: транзакция {tx_hash} сохранена в БД")
                                    except Exception as e:
                                        logger.error(f"[PIN_MONITOR] ERC20: ошибка при сохранении в БД: {e}", exc_info=True)

                                tx_status = transaction_data.get("status", "pending")

                                if tx_status == "confirmed":
                                    msg = {
                                        "msg_status": "tx_confirmed",
                                        "lang": "ru",
                                        "amount_result": transaction_data.get("amount", "N/A"),
                                        "target_address": wallet_address,
                                        "timestamp": transaction_data.get("timestamp", "N/A"),
                                    }
                                    chat_id = pin_data.get("chat_id")
                                    if chat_id:
                                        run_async_coroutine(send_telegram_notification(chat_id, msg))
                                else:
                                    logger.info(f"[PIN_MONITOR] ERC20 транзакция {tx_hash} найдена для PIN {pin_code}, статус: {tx_status}")
                        else:
                            logger.warning(f"[PIN_MONITOR] ERC20 ошибка мониторинга {wallet_address}: {result.get('error')}")
                
                except Exception as e:
                    logger.error(f"[PIN_MONITOR] Ошибка мониторинга {wallet_address}: {e}")
        
        logger.info("[PIN_MONITOR] Мониторинг PIN-кодов завершен")
        
    except Exception as e:
        logger.error(f"[PIN_MONITOR] Критическая ошибка в monitor_active_pins: {e}")