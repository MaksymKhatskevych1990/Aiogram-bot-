from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from keyboards import (
    get_city_keyboard,
    get_time_keyboard,
    get_branch_keyboard,
    get_currency_keyboard_with_back,
    get_back_keyboard,
    get_cash_operation_keyboard,
)
from utils.fiat_rates import get_usd_uah_rates
from utils.commission_calculator import commission_calculator
from google_utils import save_cash_exchange_request_to_sheet
from localization import get_message

# 💼 Состояния FSM
class CashFSM(StatesGroup):
    operation = State()  # Купить USD / Продать USD
    currency = State()
    amount = State()
    city = State()
    branch = State()
    time = State()
    name = State()
    phone = State()

# 🔁 Хендлеры поэтапно
async def start_cash(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    await message.answer(
        get_message("choose_cash_operation", lang),
        reply_markup=get_cash_operation_keyboard(lang)
    )
    await state.set_state(CashFSM.operation)

async def get_operation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    text = message.text
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    if text not in (get_message("cash_buy_usd", lang), get_message("cash_sell_usd", lang)):
        await message.answer(get_message("choose_cash_operation", lang), reply_markup=get_cash_operation_keyboard(lang))
        return
    
    await state.update_data(operation=text)
    # В этом сценарии валюта всегда USD/UAH, шаг выбора валюты пропускаем
    await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CashFSM.amount)

async def get_currency(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    # Обработка кнопки "Назад"
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text=get_message("cash_exchange", lang)), types.KeyboardButton(text=get_message("crypto_exchange", lang))],
                [types.KeyboardButton(text=get_message("back", lang))]
            ],
            resize_keyboard=True
        ))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    await state.update_data(currency=message.text)
    await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CashFSM.amount)

async def get_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_cash_operation", lang), reply_markup=get_cash_operation_keyboard(lang))
        await state.set_state(CashFSM.operation)
        return
    
    # Проверяем, что введено число
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer(get_message("invalid_amount", lang))
            return
    except ValueError:
        await message.answer(get_message("invalid_amount", lang))
        return
    
    await state.update_data(amount=amount)

    # Расчет по фиату USD↔UAH
    buy_rate, sell_rate = await get_usd_uah_rates()
    op = (data.get('operation') or '').strip()
    if buy_rate and sell_rate:
        if op == get_message("cash_buy_usd", lang):
            # Клиент покупает USD за UAH: нужен объем UAH = amount * buy_rate
            uah_to_pay = amount * sell_rate
            text = (
                f"Купить USD\n"
                f"Сумма: {amount:.2f} USD\n"
                f"Курс (покупка): {sell_rate:.2f} UAH\n"
                f"К оплате: {uah_to_pay:.2f} UAH"
            )
        else:
            # Клиент продает USD за UAH: получит UAH = amount * sell_rate
            uah_to_get = amount * buy_rate
            text = (
                f"Продать USD\n"
                f"Сумма: {amount:.2f} USD\n"
                f"Курс (продажа): {buy_rate:.2f} UAH\n"
                f"К получению: {uah_to_get:.2f} UAH"
            )
        await message.answer(text)
    else:
        await message.answer(get_message("currency_rates_error", lang))
    
    await message.answer(get_message("choose_city_branch", lang), reply_markup=get_city_keyboard(lang))
    await state.set_state(CashFSM.city)

async def get_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_cash_operation", lang), reply_markup=get_cash_operation_keyboard(lang))
        await state.set_state(CashFSM.operation)
        return
    
    await state.update_data(city=message.text)
    await message.answer(get_message("choose_branch", lang) if get_message("choose_branch", lang) else "Выберите отделение:", reply_markup=get_branch_keyboard(message.text, lang))
    await state.set_state(CashFSM.branch)

async def get_branch(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_city_branch", lang), reply_markup=get_city_keyboard(lang))
        await state.set_state(CashFSM.city)
        return
    
    await state.update_data(branch=message.text)
    await message.answer(get_message("choose_time", lang), reply_markup=get_time_keyboard(lang))
    await state.set_state(CashFSM.time)

async def get_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_branch", lang), reply_markup=get_branch_keyboard(data.get('city', ''), lang))
        await state.set_state(CashFSM.branch)
        return
    
    await state.update_data(time=message.text)
    await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CashFSM.name)

async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_time", lang), reply_markup=get_time_keyboard(lang))
        await state.set_state(CashFSM.time)
        return
    
    await state.update_data(name=message.text)
    await message.answer(get_message("enter_phone", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CashFSM.phone)

async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CashFSM.name)
        return
    
    await state.update_data(phone=message.text)
    data = await state.get_data()
    op = (data.get('operation') or '').strip()
    summary_key = "cash_withdraw_request_summary" if op == get_message("cash_buy_usd", lang) else "cash_request_summary"
    summary = get_message(
        summary_key, lang,
        currency='USD',
        amount=data['amount'],
        city=data['city'],
        branch=data['branch'],
        time=data['time'],
        name=data['name'],
        phone=data['phone'],
        username=message.from_user.username if message.from_user.username else 'N/A'
    )
    
    # Отправляем заявку администратору
    from config import ADMIN_CHAT_ID
    await message.bot.send_message(ADMIN_CHAT_ID, summary)
    
    # Сохраняем заявку в Google таблицу
    row_data = {
        'operation': data.get('operation', ''),
        'amount': data.get('amount', ''),
        'city': data.get('city', ''),
        'branch': data.get('branch', ''),
        'time': data.get('time', ''),
        'name': data.get('name', ''),
        'phone': data.get('phone', ''),
        'telegram': message.from_user.username or ''
    }
    
    success = save_cash_exchange_request_to_sheet(row_data)
    if not success:
        await message.answer("⚠️ Заявка отправлена администратору, но возникла ошибка при сохранении в таблицу")
    
    await message.answer(get_message("cash_request_success", lang))
    await state.clear()

# 🔧 Регистрация хендлеров
def register_cash_handlers(dp: Dispatcher):
    dp.message.register(start_cash, Command("cash"))
    dp.message.register(get_operation, StateFilter(CashFSM.operation))
    dp.message.register(get_currency, StateFilter(CashFSM.currency))
    dp.message.register(get_amount, StateFilter(CashFSM.amount))
    dp.message.register(get_city, StateFilter(CashFSM.city))
    dp.message.register(get_branch, StateFilter(CashFSM.branch))
    dp.message.register(get_time, StateFilter(CashFSM.time))
    dp.message.register(get_name, StateFilter(CashFSM.name))
    dp.message.register(get_phone, StateFilter(CashFSM.phone))
