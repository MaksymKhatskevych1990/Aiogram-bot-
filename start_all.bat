@echo off
echo 🚀 Запуск всех компонентов системы...
echo.

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

echo 📋 Запуск в следующем порядке:
echo 1. Celery Worker (воркер)
echo 2. Celery Beat (планировщик)
echo 3. Telegram Bot (основной бот)
echo.

echo ⚠️  ВАЖНО: Запустите каждый компонент в отдельном окне!
echo.
echo 🔧 Команды для запуска:
echo.
echo 1. Воркер:
echo    celery -A celery_app worker --loglevel=info --pool=solo --concurrency=1
echo.
echo 2. Beat:
echo    celery -A celery_app beat --loglevel=info
echo.
echo 3. Бот:
echo    python main.py
echo.

pause
