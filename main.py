import asyncio
import aiohttp
import csv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

# Replace Redis storage with in-memory storage
# from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis as AsyncRedis  # важно: async вариант

from config import TOKEN, GOOGLE_API_KEY, CSV_URL, REDIS_URL, REDIS_DB_FSM
from handlers.cash import register_cash_handlers
from handlers.crypto import register_crypto_handlers
from handlers.start import register_start_handlers
from utils.channel_rates import ChannelRatesParser

# Use in-memory storage instead of Redis
# storage = MemoryStorage()
redis_fsm =AsyncRedis.from_url(f"{REDIS_URL}/{REDIS_DB_FSM}")
storage = RedisStorage(redis=redis_fsm)

bot = Bot(token=TOKEN)
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
        print("🤖 Бот запущен...")
        await dp.start_polling(bot)
    except Exception as e:
        if "Conflict: terminated by other getUpdates request" in str(e):
            print("❌ Ошибка: Уже запущен другой экземпляр бота!")
            print("💡 Решение: Остановите все другие экземпляры бота и попробуйте снова.")
        else:
            print(f"❌ Ошибка запуска бота: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('👋 Бот остановлен')
    except Exception as e:
        if "Conflict: terminated by other getUpdates request" in str(e):
            print("❌ Ошибка: Уже запущен другой экземпляр бота!")
            print("💡 Решение: Остановите все другие экземпляры бота и попробуйте снова.")
        else:
            print(f'❌ Критическая ошибка: {e}')
