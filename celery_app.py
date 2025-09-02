from celery import Celery
from config import REDIS_URL

celery_app = Celery(
    "tasks",
    broker=f"{REDIS_URL}/0",  # брокер задач
    backend=f"{REDIS_URL}/1", # результат и статусы задач
    include=["tasks.erc20_tasks", "tasks.trc20_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-pending-every-30s-erc20": {
            "task": "tasks.erc20_tasks.periodic_check_pending_transactions_erc20",
            "schedule": 30.0,
        },
        "check-pending-every-15s-trc20": {
            "task": "tasks.trc20_tasks.periodic_check_pending_transactions_trc20",
            "schedule": 15.0,
        },
    }
)

# if __name__ == '__main__':
#     celery_app.start()