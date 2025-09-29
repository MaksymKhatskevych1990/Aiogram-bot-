# PowerShell скрипт для запуска Celery Beat
Write-Host "⏰ Запуск Celery Beat (планировщик задач)..." -ForegroundColor Green
Write-Host ""

# Активируем виртуальное окружение
& "venv\Scripts\Activate.ps1"

# Запускаем beat
Write-Host "Запуск планировщика задач..." -ForegroundColor Yellow
celery -A celery_app beat --loglevel=info

Read-Host "Нажмите Enter для выхода"
