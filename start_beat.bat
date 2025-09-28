@echo off
echo ⏰ Запуск Celery Beat (планировщик задач)...
echo.

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Запускаем beat
celery -A celery_app beat --loglevel=info

pause
