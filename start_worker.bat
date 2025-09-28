@echo off
echo 🚀 Запуск Celery Worker для Windows...
echo.

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Запускаем воркер с настройками для Windows
celery -A celery_app worker --loglevel=info --pool=solo --concurrency=1

pause
