from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
from keyboards import get_language_keyboard, get_action_keyboard, get_start_keyboard
from config import LOGO_PATH, CSV_URL
from localization import get_message
from utils.fiat_rates import get_all_currency_rates
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

    user_name = message.from_user.first_name

    if lang == "ua":
        reply = (
            f"👋 Вітаю, {user_name}!\n\n"
        )
    elif lang == "en":
        reply = (
            f"👋 Hello, {user_name}!\n\n"
        )
    else:
        reply = (
            f"👋 Привет, {user_name}!\n\n"
            
        )

    await message.answer(reply)
    await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
    await state.set_state(StartFSM.action)

# Универсальный обработчик для кнопок навигации (работает в любом состоянии)
async def handle_navigation_buttons(message: types.Message, state: FSMContext):
    """Обрабатывает кнопки навигации независимо от текущего состояния"""
    
    # ВАЖНО: Проверяем, что сообщение содержит текст
    if not message.text:
        # Если это не текстовое сообщение (например, фото), просто возвращаем False
        return False
    
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # Получаем текст кнопки "Вернуться на главную"
    back_to_main_text = get_message("back_to_main", lang)
    
    # Проверяем кнопку "Вернуться на главную"
    if back_to_main_text and back_to_main_text.strip() and back_to_main_text in message.text:
        action_message = get_message("choose_action", lang)
        if action_message:  # Проверяем, что сообщение не пустое
            await message.answer(action_message, reply_markup=get_action_keyboard(lang))
            await state.set_state(StartFSM.action)
            return True
    
    # Получаем текст кнопки "Назад"
    back_text = get_message("back", lang)
    
    # Проверяем кнопку "Назад"
    if back_text and back_text.strip() and back_text in message.text:
        # Проверяем, есть ли данные о языке
        if lang:
            start_message = get_message("please_press_start", lang)
            if start_message:  # Проверяем, что сообщение не пустое
                await message.answer(start_message, reply_markup=get_start_keyboard(lang))
            else:
                await message.answer("Пожалуйста, нажмите кнопку «Старт» для начала работы с ботом.", reply_markup=get_start_keyboard(lang))
        else:
            await message.answer("Пожалуйста, нажмите кнопку «Старт» для начала работы с ботом.", reply_markup=get_start_keyboard("ru"))
        await state.set_state(StartFSM.waiting_start)
        return True
    
    return False

# Пользователь выбирает действие
async def choose_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    action = message.text

    # Проверяем, что action не None
    if not action:
        await message.answer(get_message("invalid_action", lang))
        return

    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in action:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        await state.set_state(StartFSM.action)
        return

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
    elif get_message("current_rates", lang) in action:
        await show_current_rates(message, state)
    else:
        await message.answer(get_message("invalid_action", lang))

async def show_current_rates(message: types.Message, state: FSMContext):
    """Показывает актуальные курсы валют из канала @obmenvalut13"""
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    try:
        # Получаем курсы валют
        rates = await get_all_currency_rates()
        
        if not rates:
            await message.answer(get_message("currency_rates_error", lang))
            return
        
        # Формируем сообщение с курсами
        rates_text = get_message("rates_header", lang)
        
        # Добавляем курсы для каждой валютной пары
        currency_pairs = {
            'USD-UAH': 'USD',
            'EUR-UAH': 'EUR', 
            'GBP-UAH': 'GBP',
            'PLN-UAH': 'PLN'
        }
        
        for pair_key, currency in currency_pairs.items():
            if pair_key in rates:
                rate_data = rates[pair_key]
                rates_text += get_message("rate_format", lang).format(
                    pair=currency,
                    buy=f"{rate_data['buy']:.2f}",
                    sell=f"{rate_data['sell']:.2f}"
                ) + "\n"
            elif currency in rates:
                rate_data = rates[currency]
                rates_text += get_message("rate_format", lang).format(
                    pair=currency,
                    buy=f"{rate_data['buy']:.2f}",
                    sell=f"{rate_data['sell']:.2f}"
                ) + "\n"
        
        # Добавляем источник
        rates_text += get_message("rates_source", lang)
        
        # Показываем курсы и возвращаемся в главное меню
        await message.answer(rates_text)
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        
    except Exception as e:
        print(f"Ошибка при получении курсов: {e}")
        await message.answer(get_message("currency_rates_error", lang))
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))

# Регистрируем хендлеры
def register_start_handlers(dp: Dispatcher):
    dp.message.register(start_command, Command("start"))
    dp.message.register(handle_start_button, StateFilter(StartFSM.waiting_start))
    dp.message.register(set_language, StateFilter(StartFSM.language))
    dp.message.register(choose_action, StateFilter(StartFSM.action))
    
    # Универсальный обработчик для кнопок навигации (работает как fallback)
    # Регистрируем его с низким приоритетом и только для текстовых сообщений
    dp.message.register(
        handle_navigation_buttons, 
        lambda message: message.text is not None  # Только для текстовых сообщений
    )
