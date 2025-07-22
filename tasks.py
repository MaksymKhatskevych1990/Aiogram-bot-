# tasks.py
import redis
import json
import asyncio
from celery_app import celery_app
from networks.ethereum import check_ethereum_transaction
from google_utils import save_transaction_hash, update_transaction_status
from config import logger

# Redis для хранения статусов транзакций
r = redis.Redis(host="host.docker.internal", port=6379, db=0, decode_responses=True)


@celery_app.task
def check_erc20_confirmation_task(tx_hash, target_address, username):
    """
    Разовая проверка транзакции — обновляет статус в Redis
    """
    try:
        result = asyncio.run(check_ethereum_transaction(tx_hash, target_address))
        key = f"tx:{tx_hash}"
        logger.info("============ETH result: %s", result)


        save_transaction_hash(
            username,
            tx_hash,
            target_address,
            result["status"]
        )

        if result["success"] != True:
            logger.info(f"============Транзакция {tx_hash}: пока pending ({result['error']})")
            # обновляем статус
            r.hset(key, mapping={
                "status": "pending",
                "confirmations": result.get("confirmations", 0),
                "target_address": target_address,
                "username": username
            })
            return 
        

        
        # Если подтверждено
        # r.hset(key, mapping={
        #     "status": "confirmed",
        #     "amount": result["amount"],
        #     "from": result["from"],
        #     "to": result["to"],
        #     "timestamp": result["timestamp"],
        #     "confirmations": result["confirmations"],
        # })


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

        checked = 0
        confirmed = 0
        still_pending = 0

        for key in keys:
            logger.info("-------------------------------- key: %s", key)
            tx = r.hgetall(key)
            if not tx:
                continue

            tx_hash = key.split(":")[1]
            status = tx.get("status", "unknown")
            target_address = tx.get("target_address")
            username = tx.get("username")

            logger.info(f"[BEAT] Проверка транзакции {tx_hash}, текущий статус: {status}")


            try:
                # Синхронный вызов асинхронной функции
                result = asyncio.run(check_ethereum_transaction(tx_hash, target_address))
                checked += 1

                if result["success"] == True:
                    # ✅ Подтверждена
                    confirmed += 1
                    logger.info(f"[BEAT] Транзакция {tx_hash} подтверждена и перезаписана ✅")
                    r.delete(key)  # Удаляем ключ из Redis

                    # Сохраняем в Google Sheets
                    ok = update_transaction_status(tx_hash, "confirmed")
                    if not ok:
                        logger.error(f"[BEAT] Ошибка перезаписи транзакции {tx_hash} в Google Sheets")

                else:
                    # ⏳ Всё ещё pending
                    still_pending += 1
                    logger.info(f"[BEAT] Транзакция {tx_hash} пока pending ({result.get('error')})")
                    r.hset(key, mapping={
                        "status": "pending",
                        "confirmations": result.get("confirmations", 0),
                        "target_address": target_address,
                        "username": username
                    })

            except Exception as e:
                logger.error(f"[BEAT] Ошибка при проверке {tx_hash}: {e}")
                continue

        return {
            "checked": checked,
            "confirmed": confirmed,
            "still_pending": still_pending
        }

    except Exception as e:
        logger.error(f"[BEAT] Ошибка в periodic_check_pending_transactions: {e}")
        return {"error": str(e)}

            
"""Дальше должна быть логика перезаписи значение статуса в гугл таблицы"""