@echo off
echo Проверяю наличие запущенных экземпляров бота...
tasklist | findstr python.exe
if %errorlevel% equ 0 (
    echo Найдены запущенные процессы Python. Останавливаю их...
    taskkill /f /im python.exe
    timeout /t 2 /nobreak >nul
)

echo Запускаю бота...
cd /d "%~dp0"
python main.py
pause 