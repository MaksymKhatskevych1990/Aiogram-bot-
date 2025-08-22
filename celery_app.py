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
    beat_schedule={
        "check-pending-every-30s": {
            "task": "tasks.periodic_check_pending_transactions",
            "schedule": 20.0,
        },
    }
)

# if __name__ == '__main__':
#     celery_app.start()