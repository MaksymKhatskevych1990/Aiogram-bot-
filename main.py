import asyncio
import aiohttp
import csv
import os
import sys
import argparse
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

# Replace Redis storage with in-memory storage
# from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis as AsyncRedis  # важно: async вариант

from config import GOOGLE_API_KEY, CSV_URL, REDIS_URL, REDIS_DB_FSM, logger
from handlers.cash import register_cash_handlers
from handlers.crypto import register_crypto_handlers
from handlers.start import register_start_handlers
from utils.channel_rates import ChannelRatesParser

# Получаем токен из аргументов командной строки или из переменной окружения
def get_bot_token():
    """Получает токен бота из аргументов командной строки или переменной окружения"""
    parser = argparse.ArgumentParser(description='Запуск Telegram бота')
    parser.add_argument('--token', type=str, help='Токен бота Telegram')
    args, unknown = parser.parse_known_args()
    
    # Сначала проверяем аргумент командной строки
    if args.token:
        return args.token
    
    # Затем проверяем переменную окружения (для обратной совместимости)
    token = os.getenv('BOT_TOKEN') or os.getenv('TOKEN')
    if token:
        return token
    
    raise ValueError("BOT_TOKEN не установлен! Укажите токен через --token или переменную окружения BOT_TOKEN.")

# Получаем токен
BOT_TOKEN = get_bot_token()

# Сохраняем токен в config для использования в других модулях
from config import set_current_bot_token
set_current_bot_token(BOT_TOKEN)

if not REDIS_URL:
    raise ValueError("REDIS_URL не установлен! Установите переменную REDIS_URL в Railway.")

logger.info("🔧 Конфигурация:")
# Безопасность: не логируем полный Redis URL с паролем
redis_host = REDIS_URL.split('@')[-1].split(':')[0] if REDIS_URL and '@' in REDIS_URL else 'localhost'
logger.info(f"   - Redis Host: {redis_host}")
logger.info(f"   - Redis DB FSM: {REDIS_DB_FSM}")
logger.info(f"   - Environment: {os.getenv('ENVIRONMENT', 'development')}")
logger.info(f"   - Bot Token: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "   - Bot Token: не установлен")

# Use in-memory storage instead of Redis
# storage = MemoryStorage()
redis_fsm = AsyncRedis.from_url(REDIS_URL, db=REDIS_DB_FSM)
storage = RedisStorage(redis=redis_fsm)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
google = GOOGLE_API_KEY

# Инициализируем парсер курсов из канала
channel_rates_parser = ChannelRatesParser(bot, "@obmenvalut13")

# Делаем парсер доступным глобально
import utils.channel_rates
utils.channel_rates.channel_rates_parser = channel_rates_parser

# 👇 Регистрация всех хендлеров
def register_all_handlers(dp: Dispatcher):
    register_cash_handlers(dp)
    register_crypto_handlers(dp)
    register_start_handlers(dp)

# 🚀 Запуск бота
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        register_all_handlers(dp)
        logger.info("🤖 Бот запущен...")
        logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.debug(f"🔗 Redis: {REDIS_URL}")
        
        # Для Railway - используем webhook или polling
        if os.getenv('ENVIRONMENT') == 'production':
            logger.info("🚂 Запуск в production режиме (Railway)")
            # На Railway лучше использовать polling для простоты
            await dp.start_polling(bot)
        else:
            logger.info("💻 Запуск в development режиме")
            await dp.start_polling(bot)
            
    except Exception as e:
        if "Conflict: terminated by other getUpdates request" in str(e):
            logger.error("❌ Ошибка: Уже запущен другой экземпляр бота!")
            logger.info("💡 Решение: Остановите все другие экземпляры бота и попробуйте снова.")
        else:
            logger.error(f"❌ Ошибка запуска бота: {e}", exc_info=True)
            raise e

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('👋 Бот остановлен')
    except Exception as e:
        if "Conflict: terminated by other getUpdates request" in str(e):
            logger.error("❌ Ошибка: Уже запущен другой экземпляр бота!")
            logger.info("💡 Решение: Остановите все другие экземпляры бота и попробуйте снова.")
        else:
            logger.critical(f'❌ Критическая ошибка: {e}', exc_info=True)
            raise e
