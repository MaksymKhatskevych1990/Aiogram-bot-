from celery import Celery

celery_app = Celery(
    "tasks",
    broker="redis://host.docker.internal:6379/0",  # брокер задач
    backend="redis://host.docker.internal:6379/1", # результат и статусы задач
    include=["tasks"]
)

celery_app = Celery(
    "tasks",
    broker="redis://default:buLKeHNoBFZARkjVpNAEFbjdRLhiguts@redis.railway.internal:6379/0",  # брокер задач
    backend="redis://default:buLKeHNoBFZARkjVpNAEFbjdRLhiguts@redis.railway.internal:6379/1", # результат и статусы задач
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