@echo off
echo Останавливаю все процессы Python...
taskkill /f /im python.exe
taskkill /f /im pythonw.exe
echo Все процессы Python остановлены.
pause 