from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from keyboards import get_city_keyboard, get_time_keyboard, get_branch_keyboard, get_currency_keyboard_with_back, get_back_keyboard


# 💼 Состояния FSM
class CashFSM(StatesGroup):
    currency = State()
    amount = State()
    city = State()
    branch = State()
    time = State()
    name = State()
    phone = State()


# 🔁 Хендлеры поэтапно
async def start_cash(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите валюту:",
        reply_markup=get_currency_keyboard_with_back()
    )
    await state.set_state(CashFSM.currency)


async def get_currency(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        await message.answer("Выберите действие:", reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="💵 Обмен наличных"), types.KeyboardButton(text="💸 Обмен крипты")],
                [types.KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        ))
        # Возвращаемся к состоянию выбора действия
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    await state.update_data(currency=message.text)
    await message.answer("Введите сумму:", reply_markup=get_back_keyboard())
    await state.set_state(CashFSM.amount)


async def get_amount(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        await message.answer(
            "Выберите валюту:",
            reply_markup=get_currency_keyboard_with_back()
        )
        await state.set_state(CashFSM.currency)
        return
    
    await state.update_data(amount=message.text)
    await message.answer("Выберите город и отделение:", reply_markup=get_city_keyboard())
    await state.set_state(CashFSM.city)


async def get_city(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        await message.answer("Введите сумму:", reply_markup=get_back_keyboard())
        await state.set_state(CashFSM.amount)
        return
    
    await state.update_data(city=message.text)
    await message.answer("Выберите отделение:", reply_markup=get_branch_keyboard(message.text))
    await state.set_state(CashFSM.branch)


async def get_branch(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        data = await state.get_data()
        city = data.get('city', '')
        await message.answer("Выберите город и отделение:", reply_markup=get_city_keyboard())
        await state.set_state(CashFSM.city)
        return
    
    await state.update_data(branch=message.text)
    await message.answer("Выберите удобное время визита:", reply_markup=get_time_keyboard())
    await state.set_state(CashFSM.time)


async def get_time(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        data = await state.get_data()
        city = data.get('city', '')
        await message.answer("Выберите отделение:", reply_markup=get_branch_keyboard(city))
        await state.set_state(CashFSM.branch)
        return
    
    await state.update_data(time=message.text)
    await message.answer("Введите имя:", reply_markup=get_back_keyboard())
    await state.set_state(CashFSM.name)


async def get_name(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        await message.answer("Выберите удобное время визита:", reply_markup=get_time_keyboard())
        await state.set_state(CashFSM.time)
        return
    
    await state.update_data(name=message.text)
    await message.answer("Введите номер телефона:", reply_markup=get_back_keyboard())
    await state.set_state(CashFSM.phone)


async def get_phone(message: types.Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if "🔙 Назад" in message.text:
        await message.answer("Введите имя:", reply_markup=get_back_keyboard())
        await state.set_state(CashFSM.name)
        return
    
    await state.update_data(phone=message.text)
    data = await state.get_data()
    summary = "\n".join([
        "Новая заявка на внесение наличных:",
        f"Валюта: {data['currency']}",
        f"Сумма: {data['amount']}",
        f"Город: {data['city']}",
        f"Отделение: {data['branch']}",
        f"Время визита: {data['time']}",
        f"Имя клиента: {data['name']}",
        f"Телефон: {data['phone']}",
        f"Telegram: @{message.from_user.username if message.from_user.username else 'N/A'}"
    ])
    from config import ADMIN_CHAT_ID
    await message.bot.send_message(ADMIN_CHAT_ID, summary)
    await message.answer(
        "Спасибо! Менеджер свяжется с вами в ближайшее время для подтверждения и уточнения деталей."
    )
    await state.clear()


# 🔧 Регистрация хендлеров
def register_cash_handlers(dp: Dispatcher):
    dp.message.register(start_cash, Command("cash"))
    dp.message.register(get_currency, StateFilter(CashFSM.currency))
    dp.message.register(get_amount, StateFilter(CashFSM.amount))
    dp.message.register(get_city, StateFilter(CashFSM.city))
    dp.message.register(get_branch, StateFilter(CashFSM.branch))
    dp.message.register(get_time, StateFilter(CashFSM.time))
    dp.message.register(get_name, StateFilter(CashFSM.name))
    dp.message.register(get_phone, StateFilter(CashFSM.phone))
