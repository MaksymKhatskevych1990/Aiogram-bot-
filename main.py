import asyncio
import aiohttp
import csv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from config import TOKEN, GOOGLE_API_KEY, CSV_URL
from handlers.cash import register_cash_handlers
from handlers.crypto import register_crypto_handlers
from handlers.start import register_start_handlers

bot = Bot(token=TOKEN)
dp = Dispatcher()
google = GOOGLE_API_KEY

# 🔄 Функция для получения курса валют
# @dp.message(Command("start"))
# async def send_welcome(message: Message, from_user=None):
#     user = message.from_user.first_name
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(CSV_URL) as resp:
#                 if resp.status == 200:
#                     text_data = await resp.text()
#                     reader = csv.reader(text_data.splitlines())
#                     rows = list(reader)

#                     rates = ""
#                     for row in rows[1:]:
#                         if len(row) >= 3:
#                             a, b, c = row[0], row[1], row[2]
#                             rates += f"💱 {a}:||         {b}       /   {c}\n"

#                     reply = (
#                         f"👋 Привет! {user} Добро пожаловать в наш крипто-бот.\n\n"  
#                         "📊 Актуальные курсы валют:\n\n" +
#                         " Валюта || Покупка || Продажа \n\n"+
#                         rates +
#                         "\n🧾 Используйте /cash или /crypto для других операций."
#                     )
#                     await message.answer(reply)
#                 else:
#                     await message.answer("❌ Ошибка загрузки курсов валют. Попробуйте позже.")
#     except Exception as e:
#         print(f"Ошибка при получении курсов валют: {e}")
#         await message.answer("❌ Произошла ошибка при загрузке курсов валют. Попробуйте позже.")

# 👋 Хендлер команды /start


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
        print(f"❌ Ошибка запуска бота: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('👋 Бот остановлен')
    except Exception as e:
        print(f'❌ Критическая ошибка: {e}')
