from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
from aiogram import Bot



from google_utils import get_wallet_address, save_transaction_hash, verify_transaction, update_transaction_status
from utils.validators import is_valid_tx_hash
from utils.extract_hash_in_url import extract_tx_hash
from keyboards import get_network_keyboard_with_back, get_back_keyboard
from utils.generate_qr_code import generate_wallet_qr
from localization import get_message

from config import logger, TOKEN

bot = Bot(token=TOKEN)

async def get_bot_id() -> int:
    me = await bot.get_me()
    return me.id
WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"
# Состояния FSM
class CryptoFSM(StatesGroup):
    network = State()
    amount = State()
    transaction_hash = State()
    contact = State()
    verification = State()

# Команда /crypto
async def start_crypto(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    await message.answer(get_message("choose_network", lang), reply_markup=get_network_keyboard_with_back(lang))
    await state.set_state(CryptoFSM.network)

# Выбор сети
async def get_network(message: types.Message, state: FSMContext):
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
    await state.update_data(network=message.text)
    wallet_address = get_wallet_address(message.text)
    await state.update_data(wallet_address=wallet_address)
    if wallet_address:
        logo_path = "./img/logo.png"
        await message.answer(
            get_message("send_to_address", lang, wallet_address=wallet_address, network=message.text),
            parse_mode="Markdown"
        )
        await generate_wallet_qr(message.bot, message.chat.id, wallet_address, message.text, logo_path, lang)
    else:
        await message.answer(get_message("address_error", lang))
    await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CryptoFSM.amount)

# Ввод суммы
async def get_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_network", lang), reply_markup=get_network_keyboard_with_back(lang))
        await state.set_state(CryptoFSM.network)
        return
    await state.update_data(amount=message.text)
    await message.answer(get_message("amount_info", lang, amount=message.text))
    await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CryptoFSM.transaction_hash)

# Обработка хеша транзакции
async def get_transaction_hash(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")

    user_id = message.from_user.id
    chat_id = message.chat.id  
    bot_id = await get_bot_id()   

    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.amount)
        return
    user_input = message.text.strip()
    tx_hash = extract_tx_hash(user_input) #Проверка хэша на валидность
    if not tx_hash:
        await message.answer(get_message("invalid_tx_hash", lang))
        return
    await state.update_data(transaction_hash=tx_hash)
    await message.answer(get_message("checking_tx", lang))
    data = await state.get_data()
    network = data.get('network')
    logger.info("Получен нетворк: %s", network)
    wallet_address = get_wallet_address(network)
    if not is_valid_tx_hash(tx_hash, network): #еще одна проверка хэша на валидность
        await message.answer(get_message("invalid_tx_format", lang))
        return
    verification_result = await verify_transaction(
        tx_hash, 
        network, 
        wallet_address,
        int(user_id),
        int(chat_id),
        int(bot_id),
        lang
    )
    # if verification_result.get("success"):
    #     await state.update_data(amount_result=verification_result.get('amount', 'N/A'))
    #     await message.answer(
    #         get_message(
    #             "tx_confirmed", lang,
    #             amount=verification_result.get('amount', 'N/A'),
    #             from_addr=verification_result.get('from', 'N/A')[:10] + '...',
    #             timestamp=verification_result.get('timestamp', 'N/A')
    #         ),
    #         reply_markup=get_back_keyboard(lang)
    #     )
    #     save_transaction_hash(
    #         message.from_user.username or str(message.from_user.id),
    #         tx_hash,
    #         wallet_address,
    #         "PENDING"
    #     )
    #     await state.set_state(CryptoFSM.contact)
    # else:
    #     error_msg = verification_result.get("error", "Неизвестная ошибка")
    #     await message.answer(
    #         get_message("tx_not_confirmed", lang, error=error_msg),
    #         reply_markup=get_back_keyboard(lang)
    #     )
    #     await state.set_state(CryptoFSM.transaction_hash)

async def send_telegram_notification(chat_id: str, message):
    """
    Отправляет уведомление в Telegram пользователю о подтвержденной транзакции
    """
    try:        
        await bot.send_message(
            chat_id=chat_id, 
            text=get_message(
                message["msg_status"], 
                message["lang"],
                amount=message.get('amount_result', 'N/A'),
                from_addr=message.get('target_address'),
                timestamp=message.get('timestamp', 'N/A')
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")


# Ввод контакта
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.transaction_hash)
        return
    await state.update_data(contact=message.text)
    data = await state.get_data()
    summary = get_message(
        "crypto_request_summary", lang,
        amount=data.get('amount_result', data.get('amount', 'N/A')),
        network=data['network'],
        wallet_address=data['wallet_address'],
        tx_hash=data['transaction_hash'],
        contact=data['contact'],
        username=message.from_user.username if message.from_user.username else 'N/A'
    )
    from config import ADMIN_CHAT_ID
    await message.bot.send_message(ADMIN_CHAT_ID, summary)
    await message.answer(
        get_message("crypto_request_success", lang, summary=summary)
    )
    print(f"Отправляю сообщение администратору в чат: {ADMIN_CHAT_ID}")
    # Сохраняем заявку в Google Sheets ДО очистки state!
    # row_data = {
    #     'currency': 'USDT',  # по умолчанию
    #     'amount': data.get('amount_result', data.get('amount', '')),
    #     'network': data.get('network', ''),
    #     'wallet_address': data.get('wallet_address', ''),
    #     'visit_time': '',  # если нет - оставляем пустым
    #     'client_name': '', # если нет - оставляем пустым
    #     'phone': data.get('contact', ''),
    #     'telegram': message.from_user.username or ''
    # }

    # Пытаемся записать в таблицу
    # success = save_crypto_request_to_sheet(row_data)
    change_param = f"{str(data.get('contact', ''))}/{message.from_user.username or ''}"
    google_update_params = {
        "contact": [change_param, 9]
    }
    success = update_transaction_status(data['transaction_hash'], google_update_params)
    # if not success:
    #     await message.answer(get_message("google_sheet_error", lang))

    await state.clear()

# Регистрация хендлеров
def register_crypto_handlers(dp: Dispatcher):
    dp.message.register(start_crypto, Command("crypto"))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))

