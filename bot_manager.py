"""
Менеджер ботов - читает токены из БД и запускает отдельные процессы для каждого бота
"""
import os
import sys
import subprocess
import time
import logging
import signal
from typing import Dict, Optional
from pathlib import Path
import psutil
import aiohttp
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Путь к main.py
BOT_SCRIPT_PATH = Path(__file__).parent / "main.py"
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
CHECK_INTERVAL = int(os.getenv('BOT_MANAGER_CHECK_INTERVAL', '30'))  # Проверка каждые 30 секунд

class BotManager:
    """Менеджер для управления процессами ботов"""
    
    def __init__(self):
        self.running_bots: Dict[str, subprocess.Popen] = {}  # bot_token -> process
        self.running = True
        
    async def get_active_bots_from_db(self) -> list:
        """Получает список активных ботов из БД через backend API"""
        try:
            async with aiohttp.ClientSession() as session:
                # Получаем все боты через API
                # ВАЖНО: Этот endpoint должен быть доступен без аутентификации или с API ключом
                url = f"{BACKEND_API_URL}/bots/all-active"
                
                # Если есть API ключ для ботов
                headers = {}
                bot_api_key = os.getenv('BOT_API_KEY')
                if bot_api_key:
                    headers['X-Bot-API-Key'] = bot_api_key
                
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Ожидаем список ботов с полями: id, bot_token, status, user_id
                        return data if isinstance(data, list) else data.get('items', [])
                    else:
                        logger.error(f"Ошибка получения ботов из БД: HTTP {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Ошибка при получении ботов из БД: {e}")
            return []
    
    def is_process_running(self, process: subprocess.Popen) -> bool:
        """Проверяет, запущен ли процесс"""
        if process.poll() is not None:
            return False  # Процесс завершился
        try:
            # Проверяем через psutil
            proc = psutil.Process(process.pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def start_bot_process(self, bot_token: str, bot_id: int) -> Optional[subprocess.Popen]:
        """Запускает процесс бота с указанным токеном"""
        try:
            # Формируем команду для запуска
            python_executable = sys.executable
            env = os.environ.copy()
            env['BOT_TOKEN'] = bot_token  # Передаем токен через env для совместимости
            
            cmd = [
                python_executable,
                str(BOT_SCRIPT_PATH),
                '--token', bot_token
            ]
            
            logger.info(f"🚀 Запуск бота ID={bot_id} с токеном {bot_token[:10]}...")
            
            # Запускаем процесс в фоне
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(BOT_SCRIPT_PATH.parent)
            )
            
            logger.info(f"✅ Бот ID={bot_id} запущен (PID: {process.pid})")
            return process
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота ID={bot_id}: {e}")
            return None
    
    def stop_bot_process(self, bot_token: str, process: subprocess.Popen):
        """Останавливает процесс бота"""
        try:
            logger.info(f"🛑 Остановка бота с токеном {bot_token[:10]}... (PID: {process.pid})")
            
            # Отправляем SIGTERM для корректного завершения
            process.terminate()
            
            # Ждем до 5 секунд
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Если не завершился, убиваем принудительно
                logger.warning(f"Принудительное завершение процесса {process.pid}")
                process.kill()
                process.wait()
            
            logger.info(f"✅ Бот остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки бота: {e}")
    
    async def sync_bots(self):
        """Синхронизирует список запущенных ботов с БД"""
        # Получаем активные боты из БД
        active_bots = await self.get_active_bots_from_db()
        active_tokens = {bot['bot_token']: bot for bot in active_bots if bot.get('status') == 'active'}
        
        logger.info(f"📊 Найдено {len(active_tokens)} активных ботов в БД")
        
        # Останавливаем боты, которых больше нет в БД или они стали неактивными
        tokens_to_stop = []
        for token, process in self.running_bots.items():
            if token not in active_tokens:
                tokens_to_stop.append(token)
            elif not self.is_process_running(process):
                # Процесс упал, удаляем из списка
                logger.warning(f"⚠️ Процесс бота {token[:10]}... упал, удаляем из списка")
                tokens_to_stop.append(token)
        
        for token in tokens_to_stop:
            process = self.running_bots.pop(token, None)
            if process:
                self.stop_bot_process(token, process)
        
        # Запускаем новые боты
        for bot_data in active_bots:
            token = bot_data.get('bot_token')
            bot_id = bot_data.get('id')
            status = bot_data.get('status')
            
            if not token or status != 'active':
                continue
            
            if token not in self.running_bots:
                # Новый бот, запускаем
                process = self.start_bot_process(token, bot_id)
                if process:
                    self.running_bots[token] = process
            elif not self.is_process_running(self.running_bots[token]):
                # Процесс упал, перезапускаем
                logger.warning(f"⚠️ Перезапуск упавшего бота ID={bot_id}")
                old_process = self.running_bots.pop(token)
                if old_process:
                    self.stop_bot_process(token, old_process)
                
                process = self.start_bot_process(token, bot_id)
                if process:
                    self.running_bots[token] = process
    
    async def run(self):
        """Основной цикл менеджера"""
        logger.info("🤖 Менеджер ботов запущен")
        logger.info(f"📁 Скрипт бота: {BOT_SCRIPT_PATH}")
        logger.info(f"🔗 Backend API: {BACKEND_API_URL}")
        logger.info(f"⏱️ Интервал проверки: {CHECK_INTERVAL} секунд")
        
        # Обработчик сигналов для корректного завершения
        def signal_handler(sig, frame):
            logger.info("🛑 Получен сигнал завершения, останавливаем все боты...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                await self.sync_bots()
                
                if self.running:
                    logger.info(f"💤 Ожидание {CHECK_INTERVAL} секунд до следующей проверки...")
                    await asyncio.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("🛑 Прервано пользователем")
        finally:
            # Останавливаем все боты
            logger.info("🛑 Остановка всех ботов...")
            for token, process in list(self.running_bots.items()):
                self.stop_bot_process(token, process)
            self.running_bots.clear()
            logger.info("👋 Менеджер ботов остановлен")


if __name__ == '__main__':
    manager = BotManager()
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("👋 Менеджер ботов остановлен")

