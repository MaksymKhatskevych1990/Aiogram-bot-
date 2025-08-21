from celery import Celery
from config import REDIS_BACKEND_URL, REDIS_BROKER_URL

celery_app = Celery(
    "tasks",
    broker=REDIS_BROKER_URL,  # брокер задач
    backend=REDIS_BACKEND_URL, # результат и статусы задач
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-pending-every-30s": {
            "task": "tasks.periodic_check_pending_transactions",
            "schedule": 20.0,
        },
    }
)

if __name__ == '__main__':
    celery_app.start()