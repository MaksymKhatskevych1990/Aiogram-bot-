from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from keyboards import get_city_keyboard, get_time_keyboard, get_branch_keyboard, get_currency_keyboard_with_back, get_back_keyboard
from localization import get_message

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
    data = await state.get_data()
    lang = data.get("language", "ru")
    await message.answer(
        get_message("choose_currency", lang),
        reply_markup=get_currency_keyboard_with_back(lang)
    )
    await state.set_state(CashFSM.currency)

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
    if get_message("back", lang) in message.text:
        await message.answer(
            get_message("choose_currency", lang),
            reply_markup=get_currency_keyboard_with_back(lang)
        )
        await state.set_state(CashFSM.currency)
        return
    await state.update_data(amount=message.text)
    await message.answer(get_message("choose_city_branch", lang), reply_markup=get_city_keyboard(lang))
    await state.set_state(CashFSM.city)

async def get_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CashFSM.amount)
        return
    await state.update_data(city=message.text)
    await message.answer(get_message("choose_branch", lang) if get_message("choose_branch", lang) else "Выберите отделение:", reply_markup=get_branch_keyboard(message.text, lang))
    await state.set_state(CashFSM.branch)

async def get_branch(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    if get_message("back", lang) in message.text:
        city = data.get('city', '')
        await message.answer(get_message("choose_city_branch", lang), reply_markup=get_city_keyboard(lang))
        await state.set_state(CashFSM.city)
        return
    await state.update_data(branch=message.text)
    await message.answer(get_message("choose_time", lang), reply_markup=get_time_keyboard(lang))
    await state.set_state(CashFSM.time)

async def get_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    if get_message("back", lang) in message.text:
        city = data.get('city', '')
        await message.answer(get_message("choose_branch", lang) if get_message("choose_branch", lang) else "Выберите отделение:", reply_markup=get_branch_keyboard(city, lang))
        await state.set_state(CashFSM.branch)
        return
    await state.update_data(time=message.text)
    await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CashFSM.name)

async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
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
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CashFSM.name)
        return
    await state.update_data(phone=message.text)
    data = await state.get_data()
    summary = get_message(
        "cash_request_summary", lang,
        currency=data['currency'],
        amount=data['amount'],
        city=data['city'],
        branch=data['branch'],
        time=data['time'],
        name=data['name'],
        phone=data['phone'],
        username=message.from_user.username if message.from_user.username else 'N/A'
    )
    from config import ADMIN_CHAT_ID
    await message.bot.send_message(ADMIN_CHAT_ID, summary)
    await message.answer(get_message("cash_request_success", lang))
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
