web: python main.py
worker: celery -A celery_app worker --loglevel=info
beat: celery -A celery_app beat --loglevel=info