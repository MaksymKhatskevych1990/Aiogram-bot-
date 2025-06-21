from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from google_utils import get_wallet_address, save_transaction_hash, verify_transaction
import asyncio


WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"
# Состояния FSM
class CryptoFSM(StatesGroup):
    crypto_currency = State()
    network = State()
    amount = State()
    transaction_hash = State()  # Новое состояние для хеша транзакции
    contact = State()
    verification = State()  # Новое состояние для проверки


# Клавиатура выбора криптовалюты
def get_crypto_currency_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC"), KeyboardButton(text="ETH"), KeyboardButton(text="USDT")],
            [KeyboardButton(text="BNB"), KeyboardButton(text="XRP"), KeyboardButton(text="DOGE")],
            [KeyboardButton(text="ADA"), KeyboardButton(text="SOL"), KeyboardButton(text="TRX")],
            [KeyboardButton(text="🔍 Ввести вручную")]
        ],
        resize_keyboard=True
    )


# Клавиатура выбора сети
def get_network_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ERC20"), KeyboardButton(text="TRC20")],
            [KeyboardButton(text="BEP20"), KeyboardButton(text="Polygon")]
        ],
        resize_keyboard=True
    )


# Команда /crypto
async def start_crypto(message: types.Message, state: FSMContext):
    await message.answer("Выберите криптовалюту:", reply_markup=get_crypto_currency_keyboard())
    await state.set_state(CryptoFSM.crypto_currency)


# Выбор криптовалюты
async def get_crypto_currency(message: types.Message, state: FSMContext):
    await state.update_data(crypto_currency=message.text)
    if message.text == "🔍 Ввести вручную":
        await message.answer("Введите название криптовалюты вручную:")
        return
    await message.answer("Теперь выберите сеть:", reply_markup=get_network_keyboard())
    await state.set_state(CryptoFSM.network)


# Выбор сети
async def get_network(message: types.Message, state: FSMContext):
    await state.update_data(network=message.text)
    
    # Получаем адрес кошелька из Google Sheets
    wallet_address = get_wallet_address("Лист3", message.text)
    
    if wallet_address:
        await message.answer(
            f"💳 Отправьте криптовалюту на следующий адрес:\n\n"
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
    
    # Проверяем формат хеша
    if len(transaction_hash) < 10:
        await message.answer("❌ Неверный формат хеша транзакции. Попробуйте еще раз.")
        return
    
    await state.update_data(transaction_hash=transaction_hash)
    
    # Показываем сообщение о начале проверки
    await message.answer(
        "🔍 Проверяю транзакцию...\n"
        "⏳ Это может занять несколько секунд."
    )
    
    # Получаем данные из состояния
    data = await state.get_data()
    network = data.get('network')
    wallet_address = get_wallet_address("Лист3", network)
    
    # Проверяем транзакцию
    verification_result = await verify_transaction(
        transaction_hash, 
        network, 
        wallet_address
    )
    
    if verification_result.get("success"):
        # Транзакция подтверждена
        await message.answer(
            "✅ Транзакция подтверждена!\n\n"
            f"📊 Сумма: {verification_result.get('amount', 'N/A')}\n"
            f"👤 От: {verification_result.get('from', 'N/A')[:10]}...\n"
            f"📅 Время: {verification_result.get('timestamp', 'N/A')}\n\n"
            "Теперь укажите ваш контакт для связи (номер телефона или Telegram)."
        )
        
        # Сохраняем успешную транзакцию в Google Sheets
        save_transaction_hash(
            "Лист4", 
            transaction_hash, 
            network, 
            data.get('crypto_currency'), 
            data.get('amount'), 
            "PENDING"  # Контакт пока не указан
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

    # Обновляем контакт в Google Sheets
    save_transaction_hash(
        "Лист4", 
        data.get('transaction_hash'), 
        data.get('network'), 
        data.get('crypto_currency'), 
        data.get('amount'), 
        message.text
    )

    # Форматируем данные для отображения
    summary = "\n".join([
        f"🪙 Криптовалюта: {data['crypto_currency']}",
        f"🌐 Сеть: {data['network']}",
        f"💰 Сумма: {data['amount']}",
        f"🔍 Хеш транзакции: {data['transaction_hash']}",
        f"📞 Контакт: {data['contact']}"
    ])
    
    await message.answer(
        f"✅ Заявка на обмен принята!\n\n{summary}\n\n"
        "📞 Оператор свяжется с вами в ближайшее время.\n"
        "⏰ Обычно это занимает 5-15 минут."
    )
    
    await state.clear()


# Регистрация хендлеров
def register_crypto_handlers(dp: Dispatcher):
    dp.message.register(start_crypto, Command("crypto"))
    dp.message.register(get_crypto_currency, StateFilter(CryptoFSM.crypto_currency))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))

