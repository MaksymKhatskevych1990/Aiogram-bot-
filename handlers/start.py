from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
from keyboards import get_language_keyboard, get_action_keyboard, get_start_keyboard
from config import LOGO_PATH, CSV_URL
from localization import get_message
import aiohttp
import csv

# Шаги FSM
class StartFSM(StatesGroup):
    waiting_start = State()
    language = State()
    action = State()

# /start — показываем кнопку «Старт»
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(
        get_message("start", "ru"),  # «Нажмите кнопку Старт для начала»
        reply_markup=get_start_keyboard("ru")
    )
    await state.set_state(StartFSM.waiting_start)

# После нажатия кнопки «Старт» — логотип и выбор языка
async def handle_start_button(message: types.Message, state: FSMContext):
    text = message.text
    if text != get_message("start", "ru"):
        return

    # Отправляем логотип
    try:
        await message.answer(f"Ваш chat_id: {message.chat.id}")
        photo = types.FSInputFile(LOGO_PATH)
        await message.answer_photo(photo, caption=get_message("greeting", "ru"))
    except Exception as e:
        print(f"Ошибка при отправке логотипа: {e}")
        await message.answer(get_message("greeting", "ru"))

    # Просим выбрать язык
    await message.answer(get_message("choose_language", "ru"), reply_markup=get_language_keyboard())
    await state.set_state(StartFSM.language)

# Пользователь выбрал язык
async def set_language(message: types.Message, state: FSMContext):
    language = message.text
    if "Українська" in language:
        lang = "ua"
    elif "English" in language:
        lang = "en"
    else:
        lang = "ru"

    await state.update_data(language=lang)

    rates = await fetch_currency_rates()
    user_name = message.from_user.first_name

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

# Пользователь выбирает действие
async def choose_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    action = message.text

    # Если нажали «Назад»
    if get_message("back", lang) in action:
        await message.answer(get_message("please_press_start", lang), reply_markup=get_start_keyboard(lang))
        await state.set_state(StartFSM.waiting_start)
        return

    if get_message("cash_exchange", lang) in action or "наличн" in action:
        from handlers.cash import start_cash
        await start_cash(message, state)
    elif get_message("crypto_exchange", lang) in action or "крипт" in action:
        from handlers.crypto import start_crypto
        await start_crypto(message, state)
    else:
        await message.answer(get_message("invalid_action", lang))

# Получаем курсы валют
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

# Регистрируем хендлеры
def register_start_handlers(dp: Dispatcher):
    dp.message.register(start_command, Command("start"))
    dp.message.register(handle_start_button, StateFilter(StartFSM.waiting_start))
    dp.message.register(set_language, StateFilter(StartFSM.language))
    dp.message.register(choose_action, StateFilter(StartFSM.action))
