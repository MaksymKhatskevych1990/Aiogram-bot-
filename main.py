import asyncio
import aiohttp
import csv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from config import TOKEN, GOOGLE_API_KEY
from handlers.cash import register_cash_handlers
from handlers.crypto import register_crypto_handlers

bot = Bot(token=TOKEN)
dp = Dispatcher()
google = GOOGLE_API_KEY

# URL для получения данных в формате CSV из Google Sheets
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSg9K_pp8GbPzqdAWU0GhCEhrRsJLgpI6l6iseEVbM05TCv5oScfv8pnTmr8yagf-UlPmG2jissDJCy/pub?gid=81986874&single=true&output=csv"

# 🔄 Функция для получения курса валют
@dp.message(Command("start"))
async def send_welcome(message: Message):
    async with aiohttp.ClientSession() as session:
        async with session.get(CSV_URL) as resp:
            if resp.status == 200:
                text_data = await resp.text()
                reader = csv.reader(text_data.splitlines())
                rows = list(reader)

                rates = ""
                for row in rows[1:]:
                    if len(row) >= 3:
                        a, b, c = row[0], row[1], row[2]
                        rates += f"💱 {a}:||         {b}       /   {c}\n"

                reply = (
                    "👋 Привет! Добро пожаловать в наш крипто-бот.\n\n"  
                    "📊 Актуальные курсы валют:\n\n" +
                    " Валюта || Покупка || Продажа \n\n"+
                    rates +
                    "\n🧾 Используйте /cash или /crypto для других операций."
                )
                await message.answer(reply)
            else:
                await message.answer("Ошибка загрузки курсов валют.")

# 👋 Хендлер команды /start


# 👇 Регистрация всех хендлеров
def register_all_handlers(dp: Dispatcher):
    register_cash_handlers(dp)
    register_crypto_handlers(dp)

# 🚀 Запуск бота
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    register_all_handlers(dp)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
