from celery import Celery
from config import REDIS_URL

celery_app = Celery(
    "tasks",
    broker=f"{REDIS_URL}/0",  # брокер задач
    backend=f"{REDIS_URL}/1", # результат и статусы задач
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
        "monitor-active-pins-every-15s": {
            "task": "tasks.monitor_active_pins",
            "schedule": 15.0,
        }
    }
)

# if __name__ == '__main__':
#     celery_app.start()