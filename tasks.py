import redis
import json
import asyncio
from celery_app import celery_app
from networks.ethereum import check_ethereum_transaction, check_confirmation_for_pending
from google_utils import save_transaction_hash, update_transaction_status
import aiohttp
from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from handlers.crypto import send_telegram_notification
import redis
import json
import asyncio
import concurrent.futures
from threading import Thread
from celery_app import celery_app
from networks.ethereum import check_ethereum_transaction
from google_utils import save_transaction_hash, update_transaction_status
from config import logger

# Redis для хранения статусов транзакций
r = redis.Redis(host="host.docker.internal", port=6379, db=0, decode_responses=True)

# Глобальные переменные для event loop
_loop = None
_executor = None
_loop_thread = None

def get_or_create_event_loop():
    """Создает и запускает event loop в отдельном потоке"""
    global _loop, _executor, _loop_thread
    
    if _loop is None:
        # Создаем новый event loop
        _loop = asyncio.new_event_loop()
        
        # Функция для запуска loop'а
        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        
        # Запускаем loop в отдельном потоке
        _loop_thread = Thread(target=run_loop, daemon=True)
        _loop_thread.start()
        
        # Создаем ThreadPoolExecutor для удобной работы
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
    return _loop

def run_async_coroutine(coro):
    """Запускает корутину в общем event loop'е"""
    loop = get_or_create_event_loop()
    
    # Создаем future в указанном loop'е
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    
    # Ждем результата
    return future.result(timeout=30)  # Таймаут 30 секунд


@celery_app.task
def check_erc20_confirmation_task(tx_hash, target_address, username):
    """
    Разовая проверка транзакции — обновляет статус в Redis
    """
    try:
        # Создаем новый event loop для асинхронного вызова
        
        result = run_async_coroutine(check_ethereum_transaction(tx_hash, target_address))

        key = f"tx:{tx_hash}"
        logger.info("============ETH result: %s", result)

        save_transaction_hash(
            username,
            tx_hash,
            target_address,
            result.get("status", "pending")
        )

        if result["success"] != True:
            logger.info(f"============Транзакция {tx_hash}: пока pending ({result['error']})")
            # обновляем статус
            logger.info(f"[BEAT] 111111111111111111111111 {result.get("blockNumber", "0x0")} ")
            r.hset(key, mapping={
                "status": "pending",
                "confirmations": result.get("confirmations", 0),
                "target_address": target_address,
                "username": username,
                "blockNumber": result.get("blockNumber", "0x0"),
            })
            return
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # result = loop.run_until_complete(send_telegram_notification(username, tx_hash))
        # loop.close()
        run_async_coroutine(send_telegram_notification(username, tx_hash))

        logger.info(f"Транзакция {tx_hash} подтверждена ✅")
        # 🔥 Тут можно сразу вызывать запись в Google Sheets или отправку уведомления пользователю

    except Exception as e:
        logger.error(f"Ошибка проверки {tx_hash}: {e}")





@celery_app.task
def periodic_check_pending_transactions():
    """
    Периодически проверяет все pending транзакции в Redis
    и обновляет их статус.
    """
    try:
        keys = r.keys("tx:*")
        logger.info(f"[BEAT] Найдено транзакций: {len(keys)}")

        for key in keys:
            
            tx = r.hgetall(key)
            if not tx:
                continue

            tx_hash = key.split(":")[1]
            username = tx.get("username")
            block_number_hex = tx.get("blockNumber")

            # if not block_number_hex:
            #     logger.error(f"Отсутствует blockNumber для транзакции {tx_hash}")
            #     continue
            logger.info(f"[BEAT]block_number_hex {block_number_hex} ")

            try:
                # Создаем новый event loop для асинхронного вызова

                result = run_async_coroutine(check_confirmation_for_pending(tx_hash, block_number_hex))



                if result["success"] == True:
                    # Обработка подтвержденной транзакции
                    r.delete(key)
                    update_transaction_status(tx_hash, "confirmed")
                    run_async_coroutine(send_telegram_notification(username, tx_hash))
                    logger.info(f"[BEAT] Транзакция {tx_hash} подтверждена ✅")
                else:
                    if result["blockNumber"]:
                        r.hset(key, mapping={
                            "blockNumber": result.get("blockNumber", "0x0"),
                        })
                    logger.info(f"[BEAT] Транзакция {tx_hash} пока pending ({result["error"]})")

            except Exception as e:
                logger.error(f"[BEAT] Ошибка при проверке {tx_hash}: {e}")
                continue

    except Exception as e:
        logger.error(f"[BEAT] Ошибка в periodic_check_pending_transactions: {e}")
        return {"error": str(e)}
