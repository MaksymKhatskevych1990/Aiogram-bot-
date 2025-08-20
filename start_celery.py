#!/usr/bin/env python3
"""
Скрипт для запуска Celery worker и beat через Python
"""

import subprocess
import sys
import os

def start_celery_worker():
    """Запускает Celery worker"""
    try:
        from celery_app import celery_app
        print("🚀 Запускаю Celery worker...")
        celery_app.worker_main(['worker', '--loglevel=info'])
    except Exception as e:
        print(f"❌ Ошибка запуска Celery worker: {e}")

def start_celery_beat():
    """Запускает Celery beat"""
    try:
        from celery_app import celery_app
        print("⏰ Запускаю Celery beat...")
        celery_app.start()
    except Exception as e:
        print(f"❌ Ошибка запуска Celery beat: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "worker":
            start_celery_worker()
        elif command == "beat":
            start_celery_beat()
        else:
            print("Использование: python start_celery.py [worker|beat]")
    else:
        print("Использование: python start_celery.py [worker|beat]") 