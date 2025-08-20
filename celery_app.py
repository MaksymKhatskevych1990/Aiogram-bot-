from celery import Celery

# NOTE: Redis is required for Celery to work properly
# If you want to use Celery, you need to install and start Redis
# For now, this is commented out to prevent connection errors

# celery_app = Celery(
#     "tasks",
#     broker="redis://localhost:6379/0",  # брокер задач
#     backend="redis://localhost:6379/1", # результат и статусы задач
#     include=["tasks"]
# )

# celery_app.conf.update(
#     task_serializer="json",
#     accept_content=["json"],
#     timezone="UTC",
#     enable_utc=True,
#     beat_schedule={
#         "check-pending-every-30s": {
#             "task": "tasks.periodic_check_pending_transactions",
#             "schedule": 20.0,
#         },
#     }
# )

# Placeholder for when Redis is available
celery_app = None

if __name__ == '__main__':
    if celery_app:
        celery_app.start()
    else:
        print("Celery is disabled. Redis is required for Celery to work.")
