from celery import Celery
from config import REDISHOST, REDISPORT, REDISPASSWORD

# Формируем локальные URL для Redis
if REDISPASSWORD:
    redis_url = f"redis://:{REDISPASSWORD}@{REDISHOST}:{REDISPORT}"
else:
    redis_url = f"redis://{REDISHOST}:{REDISPORT}"

celery_app = Celery(
    "tasks",
    broker=f"{redis_url}/0",  # брокер задач
    backend=f"{redis_url}/1", # результат и статусы задач
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