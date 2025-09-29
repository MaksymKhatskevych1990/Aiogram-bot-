# PowerShell скрипт для запуска Celery Worker
Write-Host "🚀 Запуск Celery Worker для Windows..." -ForegroundColor Green
Write-Host ""

# Активируем виртуальное окружение
& "venv\Scripts\Activate.ps1"

# Запускаем воркер с настройками для Windows
Write-Host "Запуск воркера с настройками для Windows..." -ForegroundColor Yellow
celery -A celery_app worker --loglevel=info --pool=solo --concurrency=1

Read-Host "Нажмите Enter для выхода"
