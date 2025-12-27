from celery import Celery
from config import REDIS_URL
import re

# Функция для правильного формирования Redis URL с номером базы данных
def get_redis_url_with_db(db_number: int) -> str:
    """
    Формирует Redis URL с указанным номером базы данных.
    Обрабатывает случаи, когда REDIS_URL уже содержит путь к БД.
    """
    if not REDIS_URL:
        raise ValueError("REDIS_URL не установлен!")
    
    # Убираем номер БД из URL, если он есть
    # Формат: redis://user:pass@host:port/db или redis://host:port/db
    url_without_db = re.sub(r'/(\d+)$', '', REDIS_URL)
    
    # Добавляем нужный номер БД
    return f"{url_without_db}/{db_number}"

celery_app = Celery(
    "tasks",
    broker=get_redis_url_with_db(0),  # брокер задач (DB 0)
    backend=get_redis_url_with_db(1), # результат и статусы задач (DB 1)
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Настройки для Windows
    worker_pool="solo",  # Используем solo pool для Windows
    worker_concurrency=1,  # Один воркер для стабильности
    worker_prefetch_multiplier=1,  # Обрабатываем по одной задаче
    task_acks_late=True,  # Подтверждаем задачи после выполнения
    worker_disable_rate_limits=True,  # Отключаем ограничения скорости
    beat_schedule={
        "check-pending-every-30s": {
            "task": "tasks.periodic_check_pending_transactions",
            "schedule": 20.0,
        },
        "check-db-pending-every-60s": {
            "task": "tasks.periodic_check_db_pending_transactions",
            "schedule": 60.0,
        },
        "monitor-active-pins-every-15s": {
            "task": "tasks.monitor_active_pins",
            "schedule": 15.0,
        }
    }
)

# if __name__ == '__main__':
#     celery_app.start()