from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
from keyboards import get_language_keyboard, get_action_keyboard
from config import CSV_URL
import aiohttp
import csv
from localization import get_message

# Шаги FSM
class StartFSM(StatesGroup):
    language = State()
    action = State()  # Новый шаг выбора действия

# Хендлер на /start — только спрашиваем язык
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(get_message("greeting", "ru"), reply_markup=get_language_keyboard())
    await state.set_state(StartFSM.language)

# Хендлер, который срабатывает, когда пользователь выбрал язык
async def set_language(message: types.Message, state: FSMContext):
    language = message.text
    # Определяем код языка
    if "Українська" in language:
        lang = "ua"
    elif "English" in language:
        lang = "en"
    else:
        lang = "ru"
    await state.update_data(language=lang)

    rates = await fetch_currency_rates()
    user_name = message.from_user.first_name

    # Формируем текст на выбранном языке
    if lang == "ua":
        reply = (
            f"👋 Вітаю, {user_name}!\n\n"
            "📊 Актуальний курс валют:\n\n"
            " Валюта || Купівля || Продаж \n\n" +
            rates +
            "\n🧾 Використовуйте /crypto або /cash для операцій."
        )
    elif lang == "en":
        reply = (
            f"👋 Hello, {user_name}!\n\n"
            "📊 Current exchange rates:\n\n"
            " Currency || Buy || Sell \n\n" +
            rates +
            "\n🧾 Use /crypto or /cash for other operations."
        )
    else:
        reply = (
            f"👋 Привет, {user_name}!\n\n"
            "📊 Актуальные курсы валют:\n\n"
            " Валюта || Покупка || Продажа \n\n" +
            rates +
            "\n🧾 Используйте /crypto или /cash для других операций."
        )

    await message.answer(reply)
    await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
    await state.set_state(StartFSM.action)

# Функция для загрузки курсов
async def fetch_currency_rates():
    try:
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
                    return rates
    except Exception as e:
        print(f"Ошибка при получении курсов валют: {e}")
    return get_message("currency_rates_error", "ru")

async def choose_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    action = message.text
    # Обработка кнопки "Назад"
    if get_message("back", lang) in action:
        await message.answer(get_message("greeting", lang), reply_markup=get_language_keyboard())
        await state.set_state(StartFSM.language)
        return
    if get_message("cash_exchange", lang) in action or "наличн" in action:
        from handlers.cash import start_cash
        await start_cash(message, state)
    elif get_message("crypto_exchange", lang) in action or "крипт" in action:
        from handlers.crypto import start_crypto
        await start_crypto(message, state)
    else:
        await message.answer(get_message("invalid_action", lang))

# Регистрация хендлеров
def register_start_handlers(dp: Dispatcher):
    dp.message.register(start_command, Command("start"))
    dp.message.register(set_language, StateFilter(StartFSM.language))
    dp.message.register(choose_action, StateFilter(StartFSM.action))
