# PowerShell скрипт для запуска Telegram бота
Write-Host "🤖 Запуск Telegram бота..." -ForegroundColor Green
Write-Host ""

# Активируем виртуальное окружение
& "venv\Scripts\Activate.ps1"

# Запускаем бота
Write-Host "Запуск основного бота..." -ForegroundColor Yellow
python main.py

Read-Host "Нажмите Enter для выхода"
