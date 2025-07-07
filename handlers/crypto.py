from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio

from google_utils import get_wallet_address, save_transaction_hash, verify_transaction
from utils.validators import is_valid_tx_hash

from config import logger

WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"
# Состояния FSM
class CryptoFSM(StatesGroup):
    network = State()
    amount = State()
    transaction_hash = State()
    contact = State()
    verification = State()


# Клавиатура выбора сети
def get_network_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ERC20"), KeyboardButton(text="TRC20"), KeyboardButton(text="BEP20")]            
        ],
        resize_keyboard=True
    )


# Команда /crypto
async def start_crypto(message: types.Message, state: FSMContext):
    await message.answer("Выберите сеть для USDT:", reply_markup=get_network_keyboard())
    await state.set_state(CryptoFSM.network)


# Выбор сети
async def get_network(message: types.Message, state: FSMContext):
    await state.update_data(network=message.text)
    wallet_address = get_wallet_address(message.text)
    await state.update_data(wallet_address=wallet_address)
    if wallet_address:
        await message.answer(
            f"💳 Отправьте USDT на следующий адрес:\n\n"
            f"`{wallet_address}`\n\n"
            f"🌐 Сеть: {message.text}\n"
            f"⚠️ Убедитесь, что выбрали правильную сеть!",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "⚠️ Ошибка получения адреса кошелька. Пожалуйста, попробуйте позже."
        )
    await message.answer("💰 Введите сумму:")
    await state.set_state(CryptoFSM.amount)


# Ввод суммы
async def get_amount(message: types.Message, state: FSMContext):
    await state.update_data(amount=message.text)
    
    await message.answer(
        f"📊 Сумма: {message.text}\n\n"
        f"⚠️ Актуальный курс недоступен.\n"
        f"Предположим, вы получите ~XXX USD за {message.text} монет.\n"
        f"Точный расчет будет сделан оператором обменника."
    )
    
    await message.answer(
        "🔍 После отправки криптовалюты, пожалуйста, введите хеш транзакции:\n\n"
        "💡 Хеш транзакции можно найти в вашем кошельке или на сайте блокчейн-эксплорера"
    )
    
    await state.set_state(CryptoFSM.transaction_hash)


# Обработка хеша транзакции
async def get_transaction_hash(message: types.Message, state: FSMContext):
    transaction_hash = message.text.strip()
    
    
    await state.update_data(transaction_hash=transaction_hash)
    
    # Показываем сообщение о начале проверки
    await message.answer(
        "🔍 Проверяю транзакцию...\n"
        "⏳ Это может занять несколько секунд."
    )
    
    # Получаем данные из состояния
    data = await state.get_data()
    network = data.get('network')
    logger.info("Получен нетворк: %s", network)
    wallet_address = get_wallet_address(network)
    
    # Проверяем формат хеша
    if not is_valid_tx_hash(transaction_hash, network):
        await message.answer("❌ Неверный формат хеша транзакции. Попробуйте еще раз.")
        return
    
    # Проверяем транзакцию
    verification_result = await verify_transaction(
        transaction_hash, 
        network, 
        wallet_address
    )
    
    if verification_result.get("success"):
        # Транзакция подтверждена
        await state.update_data(amount_result=verification_result.get('amount', 'N/A'))
        await message.answer(
            "✅ Транзакция подтверждена!\n\n"
            f"📊 Сумма: {verification_result.get('amount', 'N/A')}\n"
            f"👤 От: {verification_result.get('from', 'N/A')[:10]}...\n"
            f"📅 Время: {verification_result.get('timestamp', 'N/A')}\n\n"
            "Теперь укажите ваш контакт для связи (номер телефона или Telegram)."
        )
        
        # Сохраняем успешную транзакцию в Google Sheets
        save_transaction_hash(
            message.from_user.username or str(message.from_user.id),
            transaction_hash,
            wallet_address,
            "PENDING"
        )
        
        await state.set_state(CryptoFSM.contact)
        
    else:
        # Транзакция не подтверждена
        error_msg = verification_result.get("error", "Неизвестная ошибка")
        await message.answer(
            f"❌ Транзакция не подтверждена!\n\n"
            f"🔍 Ошибка: {error_msg}\n\n"
            "Возможные причины:\n"
            "• Транзакция еще не прошла\n"
            "• Неверный хеш транзакции\n"
            "• Транзакция отправлена на другой адрес\n"
            "• Проблемы с сетью\n\n"
            "Попробуйте еще раз или обратитесь в поддержку."
        )
        
        # Возвращаемся к вводу хеша
        await state.set_state(CryptoFSM.transaction_hash)


# Ввод контакта
async def get_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    data = await state.get_data()
    # Формируем заявку для админа
    summary = "\n".join([
        "Новая заявка на обмен USDT:",
        f"Валюта: USDT",
        f"Сумма: {data.get('amount_result', data.get('amount', 'N/A'))}",
        f"Сеть: {data['network']}",
        f"Адрес кошелька: {data['wallet_address']}",
        f"Хеш транзакции: {data['transaction_hash']}",
        f"Контакт: {data['contact']}",
        f"Telegram: @{message.from_user.username if message.from_user.username else 'N/A'}"
    ])
    # Отправка админу
    from config import ADMIN_CHAT_ID
    await message.bot.send_message(ADMIN_CHAT_ID, summary)
    # Ответ клиенту
    await message.answer(
        f"✅ Заявка на обмен принята!\n\n{summary}\n\n"
        "📞 Оператор свяжется с вами в ближайшее время.\n"
        "⏰ Обычно это занимает 5-15 минут."
    )
    await state.clear()


# Регистрация хендлеров
def register_crypto_handlers(dp: Dispatcher):
    dp.message.register(start_crypto, Command("crypto"))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))

