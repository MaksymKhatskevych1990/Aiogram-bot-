from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
from aiogram import Bot
import random
import redis
from datetime import datetime, timedelta
import json

from google_utils import get_wallet_address, save_transaction_hash, verify_transaction, update_transaction_status
from utils.validators import is_valid_tx_hash
from utils.extract_hash_in_url import extract_tx_hash
from keyboards import get_network_keyboard_with_back, get_back_keyboard, get_crypto_operation_keyboard, get_action_keyboard, get_pin_generation_keyboard
from utils.generate_qr_code import generate_wallet_qr
from utils.commission_calculator import commission_calculator
from localization import get_message

from config import logger, TOKEN, REDIS_URL

bot = Bot(token=TOKEN)

async def get_bot_id() -> int:
    me = await bot.get_me()
    return me.id

WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"

# Инициализация Redis для PIN-кодов
redis_client = redis.from_url(REDIS_URL, db=5, decode_responses=True) if REDIS_URL else None

# Состояния FSM
class CryptoFSM(StatesGroup):
    operation = State()  # Купить USDT / Продать USDT
    network = State()
    amount = State()
    # pin_generation = State()  # УБИРАЕМ - PIN генерируется в get_network
    pin_verification = State()  # Проверка PIN-кода
    client_wallet = State()  # для режима "Купить USDT"
    transaction_hash = State()  # для режима "Продать USDT"
    client_name = State()  # для режима "Купить USDT" - имя пользователя
    contact = State()
    verification = State()

# Функции для работы с PIN-кодами
def generate_pin_code() -> str:
    """Генерирует случайный 5-значный PIN-код"""
    return str(random.randint(10000, 99999))

def save_pin_code(user_id: int, pin_code: str) -> bool:
    """Сохраняет PIN-код для пользователя в Redis"""
    if not redis_client:
        logger.error("Redis недоступен для сохранения PIN-кода")
        return False
    
    try:
        # Сохраняем PIN-код с TTL 1 час
        key = f"pin_code:{user_id}"
        redis_client.setex(key, 3600, pin_code)
        logger.info(f"PIN-код {pin_code} сохранен для пользователя {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения PIN-кода: {e}")
        return False

def verify_pin_code(user_id: int, input_pin: str) -> bool:
    """Проверяет PIN-код пользователя"""
    if not redis_client:
        logger.error("Redis недоступен для проверки PIN-кода")
        return False
    
    try:
        key = f"pin_code:{user_id}"
        stored_pin = redis_client.get(key)
        
        if not stored_pin:
            logger.warning(f"PIN-код не найден для пользователя {user_id}")
            return False
        
        is_valid = stored_pin == input_pin
        if is_valid:
            # Удаляем PIN-код после успешной проверки
            redis_client.delete(key)
            logger.info(f"PIN-код успешно проверен и удален для пользователя {user_id}")
        else:
            logger.warning(f"Неверный PIN-код для пользователя {user_id}")
        
        return is_valid
    except Exception as e:
        logger.error(f"Ошибка проверки PIN-кода: {e}")
        return False

# Функции для системы безопасности с IP-привязкой
def get_user_ip(message: types.Message) -> str:
    """Получает IP-адрес пользователя"""
    try:
        # Пытаемся получить IP из заголовков (если доступно)
        if hasattr(message, 'from_user') and hasattr(message.from_user, 'ip_address'):
            return message.from_user.ip_address
        
        # Альтернативный способ - через внешний сервис
        # (это потребует дополнительной настройки)
        return "unknown"
    except Exception:
        return "unknown"

def save_pin_code_with_ip(user_id: int, pin_code: str, ip_address: str, network: str, amount: float, wallet_address: str) -> bool:
    """Сохраняет PIN-код с привязкой к IP-адресу"""
    if not redis_client:
        logger.error("Redis недоступен для сохранения PIN-кода")
        return False
    
    try:
        # Создаем уникальный ключ сессии
        session_id = f"session:{user_id}:{int(datetime.now().timestamp())}"
        
        # Сохраняем данные сессии с IP-привязкой
        session_data = {
            'user_id': user_id,
            'pin_code': pin_code,
            'ip_address': ip_address,
            'network': network,
            'amount': amount,
            'wallet_address': wallet_address,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=2)).isoformat(),
            'status': 'active'
        }
        
        # Сохраняем сессию на 2 часа
        redis_client.setex(session_id, 7200, json.dumps(session_data))
        
        # Также сохраняем обратную связь PIN -> session_id
        pin_key = f"pin_session:{user_id}:{pin_code}"
        redis_client.setex(pin_key, 7200, session_id)
        
        logger.info(f"PIN-код с IP-привязкой сохранен для пользователя {user_id}, IP: {ip_address}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения PIN-кода с IP: {e}")
        return False

def verify_pin_code_with_ip(user_id: int, input_pin: str, current_ip: str) -> dict:
    """Проверяет PIN-код с проверкой IP-адреса"""
    if not redis_client:
        return {"valid": False, "error": "Redis недоступен"}
    
    try:
        # Находим сессию по PIN-коду
        pin_key = f"pin_session:{user_id}:{input_pin}"
        session_id = redis_client.get(pin_key)
        
        if not session_id:
            return {"valid": False, "error": "PIN-код не найден или истек"}
        
        # Получаем данные сессии
        session_data_str = redis_client.get(session_id)
        if not session_data_str:
            return {"valid": False, "error": "Сессия не найдена"}
        
        session_data = json.loads(session_data_str)
        
        # Проверяем IP-адрес
        stored_ip = session_data.get('ip_address', '')
        if stored_ip != "unknown" and stored_ip != current_ip:
            logger.warning(f"Попытка использования PIN-кода с другого IP: {current_ip} != {stored_ip}")
            return {"valid": False, "error": "PIN-код может быть использован только с того же устройства"}
        
        # Проверяем статус сессии
        if session_data.get('status') != 'active':
            return {"valid": False, "error": "Сессия неактивна"}
        
        # Проверяем срок действия
        expires_at = datetime.fromisoformat(session_data.get('expires_at', ''))
        if datetime.now() > expires_at:
            return {"valid": False, "error": "PIN-код истек"}
        
        # Удаляем PIN-код после успешной проверки
        redis_client.delete(pin_key)
        session_data['status'] = 'verified'
        redis_client.setex(session_id, 7200, json.dumps(session_data))
        
        logger.info(f"PIN-код успешно проверен с IP {current_ip} для пользователя {user_id}")
        return {"valid": True, "session_data": session_data}
        
    except Exception as e:
        logger.error(f"Ошибка проверки PIN-кода с IP: {e}")
        return {"valid": False, "error": "Ошибка проверки PIN-кода"}

async def validate_transaction_ownership(tx_hash: str, user_id: int, expected_amount: float, network: str) -> dict:
    """Проверяет принадлежность транзакции пользователю"""
    try:
        if not redis_client:
            return {"valid": False, "error": "Redis недоступен"}
            
        # Получаем данные сессии пользователя
        pattern = f"session:*"
        keys = redis_client.keys(pattern)
        
        for key in keys:
            session_data_str = redis_client.get(key)
            if session_data_str:
                session_data = json.loads(session_data_str)
                if (session_data.get('user_id') == user_id and 
                    session_data.get('status') == 'verified'):
                    
                    # Проверяем соответствие параметров транзакции
                    if (session_data.get('network') == network and
                        abs(float(session_data.get('amount', 0)) - expected_amount) < 0.01):
                        return {"valid": True, "session_data": session_data}
        
        return {"valid": False, "error": "Транзакция не соответствует вашей сессии"}
        
    except Exception as e:
        logger.error(f"Ошибка проверки принадлежности транзакции: {e}")
        return {"valid": False, "error": "Ошибка проверки транзакции"}

def check_suspicious_activity(user_id: int, ip_address: str) -> dict:
    """Проверяет подозрительную активность"""
    try:
        if not redis_client:
            return {"suspicious": False}
            
        # Проверяем количество активных сессий с этого IP
        pattern = f"session:*"
        keys = redis_client.keys(pattern)
        
        ip_sessions = 0
        user_sessions = 0
        
        for key in keys:
            session_data_str = redis_client.get(key)
            if session_data_str:
                session_data = json.loads(session_data_str)
                if session_data.get('ip_address') == ip_address:
                    ip_sessions += 1
                if session_data.get('user_id') == user_id:
                    user_sessions += 1
        
        # Проверяем лимиты
        if ip_sessions > 10:  # Максимум 3 активные сессии с одного IP
            return {"suspicious": True, "reason": "Слишком много активных сессий с этого IP"}
        
        if user_sessions > 3:  # Максимум 1 активная сессия на пользователя
            return {"suspicious": True, "reason": "У вас уже есть активная сессия"}
        
        return {"suspicious": False}
        
    except Exception as e:
        logger.error(f"Ошибка проверки подозрительной активности: {e}")
        return {"suspicious": False}

def check_transaction_hash_uniqueness(tx_hash: str) -> dict:
    """Проверяет, не использовался ли уже этот хеш транзакции"""
    try:
        if not redis_client:
            return {"unique": True, "error": None}
        
        # Проверяем в Redis, есть ли уже такой хеш
        hash_key = f"used_hash:{tx_hash}"
        existing_hash = redis_client.get(hash_key)
        
        if existing_hash:
            # Хеш уже используется
            try:
                hash_data = json.loads(existing_hash)
                used_by_user = hash_data.get('user_id', 'unknown')
                used_at = hash_data.get('used_at', 'unknown')
                logger.warning(f"Попытка повторного использования хеша {tx_hash} пользователем {used_by_user}")
                return {
                    "unique": False, 
                    "error": f"Ты лузер! Этот хеш уже использовался пользователем {used_by_user} в {used_at}",
                    "used_by": used_by_user,
                    "used_at": used_at
                }
            except json.JSONDecodeError:
                # Если данные повреждены, все равно считаем хеш использованным
                return {"unique": False, "error": "Ты лузер! Этот хеш уже использовался ранее"}
        
        return {"unique": True, "error": None}
        
    except Exception as e:
        logger.error(f"Ошибка проверки уникальности хеша: {e}")
        return {"unique": True, "error": None}

def mark_transaction_hash_as_used(tx_hash: str, user_id: int, network: str) -> bool:
    """Отмечает хеш транзакции как использованный"""
    try:
        if not redis_client:
            return False
        
        hash_key = f"used_hash:{tx_hash}"
        hash_data = {
            'user_id': user_id,
            'network': network,
            'used_at': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Сохраняем на 30 дней
        redis_client.setex(hash_key, 30 * 24 * 3600, json.dumps(hash_data))
        logger.info(f"Хеш {tx_hash} отмечен как использованный пользователем {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при отметке хеша как использованного: {e}")
        return False

# Команда /crypto
async def start_crypto(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    await message.answer(get_message("choose_crypto_operation", lang), reply_markup=get_crypto_operation_keyboard(lang))
    await state.set_state(CryptoFSM.operation)

async def set_crypto_operation(message: types.Message, state: FSMContext):
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
    
    if text not in (get_message("crypto_buy_usdt", lang), get_message("crypto_sell_usdt", lang)):
        await message.answer(get_message("choose_crypto_operation", lang), reply_markup=get_crypto_operation_keyboard(lang))
        return
    await state.update_data(operation=text)
    await message.answer(get_message("choose_network", lang), reply_markup=get_network_keyboard_with_back(lang))
    await state.set_state(CryptoFSM.network)

# Выбор сети
async def get_network(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_crypto_operation", lang), reply_markup=get_crypto_operation_keyboard(lang))
        await state.set_state(CryptoFSM.operation)
        return
    
    # Проверяем, что выбрана правильная сеть
    if message.text not in ["ERC20", "TRC20"]:
        await message.answer(get_message("choose_network", lang), reply_markup=get_network_keyboard_with_back(lang))
        return
    
    await state.update_data(network=message.text)
    
    # Проверяем, какая операция выбрана
    operation_data = await state.get_data()
    operation = operation_data.get('operation', '').strip()
    
    # QR код и адрес кошелька показываем только при продаже USDT
    if operation == get_message("crypto_sell_usdt", operation_data.get("language", "ru")):
        wallet_address = get_wallet_address(message.text)
        await state.update_data(wallet_address=wallet_address)
        
        if wallet_address:
            logo_path = "img/logo-qr.png"
            await message.answer(
                get_message("send_to_address", operation_data.get("language", "ru"), wallet_address=wallet_address, network=message.text),
                parse_mode="Markdown"
            )
            await generate_wallet_qr(message.bot, message.chat.id, wallet_address, message.text, logo_path, operation_data.get("language", "ru"))
            
            # НОВОЕ: Генерируем PIN-код сразу после показа адреса кошелька
            user_ip = get_user_ip(message)
            user_id = message.from_user.id
            
            # Проверяем подозрительную активность
            activity_check = check_suspicious_activity(user_id, user_ip)
            
            if activity_check["suspicious"]:
                await message.answer(f"❌ {activity_check['reason']}")
                await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
                from handlers.start import StartFSM
                await state.set_state(StartFSM.action)
                return
            
            # Генерируем PIN-код с IP-привязкой (пока без суммы, добавим её позже)
            pin_code = generate_pin_code()
            
            # Сохраняем PIN-код с базовыми данными (сумму добавим позже)
            if save_pin_code_with_ip(user_id, pin_code, user_ip, message.text, 0, wallet_address):
                await state.update_data(generated_pin=pin_code, pin_generated=True)
                await message.answer(
                    f"🔐 **PIN-код для вашей транзакции:** `{pin_code}`\n\n"
                    f"⚠️ **ВАЖНО:** Этот PIN-код привязан к вашему устройству и может быть использован только вами!",
                    parse_mode="Markdown"
                )
                
                # ВАЖНО: Переходим к вводу суммы с правильной клавиатурой
                await message.answer(get_message("enter_amount", operation_data.get("language", "ru")), reply_markup=get_back_keyboard(operation_data.get("language", "ru")))
                await state.set_state(CryptoFSM.amount)
                return
            else:
                await message.answer(get_message("pin_generation_error", lang))
                return
        else:
            await message.answer(get_message("address_error", operation_data.get("language", "ru")))
            return
    
    # Для покупки USDT переходим к вводу суммы
    await message.answer(get_message("enter_amount", operation_data.get("language", "ru")), reply_markup=get_back_keyboard(operation_data.get("language", "ru")))
    
    # ОТЛАДКА: логируем переход к состоянию amount
    logger.info(f"[DEBUG] get_network: переходим в состояние CryptoFSM.amount")
    await state.set_state(CryptoFSM.amount)

# Ввод суммы
async def get_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ОТЛАДКА: логируем вызов функции
    current_state = await state.get_state()
    logger.info(f"[DEBUG] get_amount вызвана в состоянии: {current_state}")
    logger.info(f"[DEBUG] Текст сообщения: '{message.text}'")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("choose_network", lang), reply_markup=get_network_keyboard_with_back(lang))
        await state.set_state(CryptoFSM.network)
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
    
    # Получаем обновленные данные
    data = await state.get_data()
    operation = data.get('operation', '').strip()
    
    # Проверяем, какая операция выбрана
    if operation == get_message("crypto_sell_usdt", lang):
        # Для продажи USDT показываем комиссию и переходим к проверке PIN
        network = data.get('network', '')
        
        # ИСПРАВЛЕНО: Правильно вызываем метод calculate_commission
        commission_result = commission_calculator.calculate_commission("USDT_to_USD", amount)
        
        if commission_result['success']:
            commission_amount = commission_result['commission_amount']
            final_amount = commission_result['final_amount']
            
            await message.answer(
                f"💰 **Сумма:** {amount} USDT\n"
                f"🌐 **Сеть:** {network}\n"
                f"💸 **Комиссия:** {commission_amount} USDT\n"
                f"💵 **К получению:** {final_amount} USDT",
                parse_mode="Markdown"
            )
        else:
            # Если ошибка расчета комиссии, показываем базовую информацию
            await message.answer(
                f"💰 **Сумма:** {amount} USDT\n"
                f"🌐 **Сеть:** {network}\n"
                f"⚠️ **Комиссия будет рассчитана менеджером**",
                parse_mode="Markdown"
            )
        
        # Обновляем данные PIN-кода с суммой
        if data.get('pin_generated'):
            pin_code = data.get('generated_pin')
            user_id = message.from_user.id
            user_ip = get_user_ip(message)
            network = data.get('network', '')
            wallet_address = data.get('wallet_address', '')
            
            # Обновляем сессию с новой суммой
            await update_pin_session_with_amount(user_id, pin_code, amount)
        
        # Переходим к проверке PIN-кода
        await message.answer(get_message("enter_pin", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.pin_verification)
    else:
        # Для покупки USDT продолжаем старую логику
        await message.answer(get_message("enter_wallet_address", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.client_wallet)

# Проверка PIN-кода (теперь вызывается после ввода суммы)
async def verify_pin(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.amount)
        return
    
    # Получаем IP-адрес пользователя
    user_ip = get_user_ip(message)
    
    # Проверяем PIN-код с IP-привязкой
    user_id = message.from_user.id
    input_pin = message.text.strip()
    
    # Проверяем формат PIN-кода (5 цифр)
    if not input_pin.isdigit() or len(input_pin) != 5:
        await message.answer(
            get_message("invalid_pin_format", lang),
            reply_markup=get_back_keyboard(lang)
        )
        return
    
    verification_result = verify_pin_code_with_ip(user_id, input_pin, user_ip)
    
    if verification_result["valid"]:
        # PIN-код верный, сохраняем данные транзакции в Google Sheets
        await save_transaction_data_to_trc_sheet(state, user_id, input_pin, message)
        
        # Переходим к вводу хеша транзакции
        await message.answer(
            get_message("pin_verified", lang),
            reply_markup=get_back_keyboard(lang)
        )
        await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.transaction_hash)
    else:
        # PIN-код неверный
        await message.answer(f"❌ {verification_result['error']}")
        await message.answer(get_message("enter_pin", lang), reply_markup=get_back_keyboard(lang))

async def save_transaction_data_to_trc_sheet(state: FSMContext, user_id: int, pin_code: str, message: types.Message):
    """Сохраняет данные транзакции в лист TRC с PIN-кодом (номер телефона будет добавлен позже)"""
    try:
        data = await state.get_data()
        
        # Получаем данные из состояния
        transaction_data = {
            'amount': data.get('amount', ''),
            'initiator_user_id': user_id,
            'tx_hash_user_id': user_id,  # Пока тот же пользователь
            'network': data.get('network', ''),
            'operation': data.get('operation', ''),
            'tx_hash': '',  # Пока пустой, заполнится при вводе хеша
            'started_at': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'status': 'PIN_VERIFIED',  # Статус после проверки PIN
            'pin_code': pin_code,
            'phone_number': ''  # Пока пустой, заполнится после верификации транзакции
        }
        
        # Сохраняем в Google Sheets
        from google_utils import save_trc_transaction_tracking_to_sheet
        success = save_trc_transaction_tracking_to_sheet(transaction_data)
        
        if success:
            logger.info(f"✅ Данные транзакции с PIN-кодом сохранены для пользователя {user_id}")
            # Сохраняем user_id в состоянии для последующего обновления номера телефона
            await state.update_data(trc_sheet_user_id=user_id)
        else:
            logger.error(f"❌ Ошибка сохранения данных транзакции для пользователя {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении данных транзакции: {e}")

# Ввод имени пользователя (для покупки USDT)
async def get_client_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        # Возврат к вводу суммы для покупки
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.amount)
        return
    
    # Сохраняем имя пользователя
    await state.update_data(client_name=message.text.strip())
    
    # Теперь спрашиваем номер телефона
    await message.answer(get_message("enter_phone", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CryptoFSM.contact)

async def get_client_wallet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.amount)
        return
    await state.update_data(client_wallet=message.text.strip())
    await message.answer(get_message("enter_phone", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(CryptoFSM.contact)

# Обработка хеша транзакции
async def get_transaction_hash(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ОТЛАДКА: логируем текущее состояние и данные
    current_state = await state.get_state()
    logger.info(f"[DEBUG] get_transaction_hash вызвана в состоянии: {current_state}")
    logger.info(f"[DEBUG] Данные состояния: {data}")
    logger.info(f"[DEBUG] Текст сообщения: '{message.text}'")
    
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        # ИСПРАВЛЕНО: Возвращаемся к проверке PIN-кода
        await message.answer(get_message("enter_pin", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.pin_verification)
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id  
    bot_id = await get_bot_id()   

    user_input = message.text.strip()
    tx_hash = extract_tx_hash(user_input)
    if not tx_hash:
        await message.answer(get_message("invalid_tx_hash", lang))
        return
    
    # НОВОЕ: Проверяем уникальность хеша транзакции
    uniqueness_check = check_transaction_hash_uniqueness(tx_hash)
    if not uniqueness_check["unique"]:
        await message.answer(f"❌ {uniqueness_check['error']}")
        # Возвращаемся в главное меню, так как это серьезное нарушение
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    # Получаем данные транзакции для проверки принадлежности
    network = data.get('network', '')
    amount = data.get('amount', 0)
    
    # Проверяем принадлежность транзакции пользователю
    ownership_check = await validate_transaction_ownership(tx_hash, user_id, amount, network)
    
    if not ownership_check["valid"]:
        await message.answer(f"❌ {ownership_check['error']}")
        await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
        return
    
    await state.update_data(transaction_hash=tx_hash)
    await message.answer(get_message("checking_tx", lang))
    
    data = await state.get_data()
    network = data.get('network')
    logger.info("Получен нетворк: %s", network)
    wallet_address = get_wallet_address(network)
    
    if not is_valid_tx_hash(tx_hash, network):
        await message.answer(get_message("invalid_tx_format", lang))
        return
    
    # Обновляем хеш транзакции в Google Sheets
    await update_trc_transaction_hash_in_sheet(tx_hash)
    
    verification_result = await verify_transaction(
        tx_hash, 
        network, 
        wallet_address,
        int(user_id),
        int(chat_id),
        int(bot_id),
        lang
    )
    
    # Обрабатываем результат проверки транзакции
    if verification_result.get('success'):
        if verification_result.get('status') == 'processing':
            # Транзакция передана в асинхронную обработку
            await message.answer(get_message("transaction_processing", lang))
            # Обновляем хеш транзакции в Google Sheets
            await update_trc_transaction_hash_in_sheet(tx_hash)
            # Возвращаемся в главное меню, так как результат придет через уведомление
            await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
            from handlers.start import StartFSM
            await state.set_state(StartFSM.action)
        else:
            # Синхронная обработка (для совместимости)
            mark_transaction_hash_as_used(tx_hash, user_id, network)
            await update_trc_transaction_status_in_sheet(tx_hash, 'COMPLETED')
            await message.answer(get_message("transaction_verified", lang))
            await message.answer(get_message("enter_contact", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.contact)
    else:
        await update_trc_transaction_status_in_sheet(tx_hash, 'FAILED')
        await message.answer(f"❌ {verification_result.get('error', 'Ошибка проверки транзакции')}")

async def update_trc_transaction_hash_in_sheet(tx_hash: str):
    """Обновляет хеш транзакции в Google Sheets"""
    try:
        from google_utils import update_transaction_status
        # Используем функцию update_transaction_status для обновления хеша транзакции
        google_update_params = {
            "tx_hash": [tx_hash, 6]  # Колонка 6 для хеша транзакции
        }
        success = update_transaction_status('', google_update_params)  # Пустой tx_hash для поиска
        if success:
            logger.info(f"✅ Хеш транзакции {tx_hash} обновлен в Google Sheets")
        else:
            logger.error(f"❌ Ошибка обновления хеша транзакции {tx_hash}")
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении хеша транзакции: {e}")

async def update_trc_transaction_status_in_sheet(tx_hash: str, status: str):
    """Обновляет статус транзакции в Google Sheets"""
    try:
        from google_utils import update_transaction_status
        # Используем функцию из google_utils.py вместо дублирующей
        google_update_params = {
            "status": [status, 8]  # Колонка 8 для статуса
        }
        success = update_transaction_status(tx_hash, google_update_params)
        if success:
            logger.info(f"✅ Статус транзакции {tx_hash} обновлен на {status}")
        else:
            logger.error(f"❌ Ошибка обновления статуса транзакции {tx_hash}")
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении статуса транзакции: {e}")

async def send_telegram_notification(chat_id: str, msg):
    from aiogram import Bot
    from config import logger, TOKEN
    
    bot = Bot(token=TOKEN)
    """
    Отправляет уведомление в Telegram пользователю о подтвержденной транзакции
    """
    
    try:
        # Проверяем, есть ли специальное сообщение об ошибке
        if msg.get("msg_status") == "hash_already_used":
            await bot.send_message(
                chat_id=chat_id,
                text=msg.get("error", "❌ Ты лузер! Этот хеш уже использовался.")
            )
        elif msg.get("msg_status") == "tx_failed":
            await bot.send_message(
                chat_id=chat_id,
                text=get_message(
                    "tx_failed",
                    msg["lang"],
                    error=msg.get("error", "Неизвестная ошибка")
                )
            )
        else:
            await bot.send_message(
                chat_id=chat_id, 
                text=get_message(
                    msg["msg_status"], 
                    msg["lang"],
                    amount=msg.get('amount_result', 'N/A'),
                    from_addr=msg.get('target_address'),
                    timestamp=msg.get('timestamp', 'N/A')
                )
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")


# Ввод контакта
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    logger.info(f"[crypto] -------   get_contact data: {data}")
    # ВАЖНО: сначала проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    # Проверяем, откуда пришел пользователь
    op = (data.get('operation') or '').strip()
    logger.info(f"[crypto] -------   get_contact op: {op}")
    if get_message("back", lang) in message.text:
        if op == get_message("crypto_buy_usdt", lang):
            # Возврат к вводу имени для покупки
            await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.client_name)
        else:
            # ИСПРАВЛЕНО: Для продажи USDT возвращаемся к вводу хеша транзакции
            await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.transaction_hash)
        return
    
    await state.update_data(contact=message.text)
    
    if op == get_message("crypto_buy_usdt", lang):
        # Для покупки USDT - показываем итоговую информацию и отправляем администратору
        summary = (
            f"🟢 *Новая заявка: Купить USDT*\n\n"
            f"👤 Имя: {data.get('client_name', 'Не указано')}\n"
            f"🌐 Сеть: {data.get('network', '')}\n"
            f"🎯 Желаемая сумма: {data.get('usdt_amount', '')} USDT\n"
            f"💵 К оплате: {data.get('usd_to_pay', '')} USD\n"
            f"📱 Телефон: {data.get('contact', '')}\n"
            f"👤 Telegram: @{message.from_user.username if message.from_user.username else 'N/A'}"
        )
        
        # Отправляем администратору
        from config import ADMIN_CHAT_ID
        await message.bot.send_message(ADMIN_CHAT_ID, summary, parse_mode="Markdown")
        
        # Показываем пользователю подтверждение
        await message.answer(
            f"✅ *Заявка на покупку USDT отправлена!*\n\n"
            f"👤 Имя: {data.get('client_name', 'Не указано')}\n"
            f"🎯 Сумма: {data.get('usdt_amount', '')} USDT\n"
            f"💵 К оплате: {data.get('usd_to_pay', '')} USD\n"
            f"🌐 Сеть: {data.get('network', '')}\n\n"
            f"📞 Наш менеджер свяжется с вами в ближайшее время для уточнения деталей.",
            parse_mode="Markdown"
        )
        
        # Показываем главное меню вместо очистки состояния
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        
    else:
        # Для продажи USDT - продолжаем по старому сценарию
        data = await state.get_data()
        
        # Обновляем номер телефона в TRC листе Google Sheets
        user_id = data.get('trc_sheet_user_id')
        if user_id and data.get('contact'):
            from google_utils import update_transaction_status
            # Используем функцию update_transaction_status для обновления номера телефона
            google_update_params = {
                "phone": [data.get('contact'), 12]  # Колонка 12 для номера телефона
            }
            update_transaction_status('', google_update_params)  # Пустой tx_hash, так как обновляем по user_id
        
        summary = get_message(
            "crypto_request_summary", lang,
            amount=data.get('amount_result', data.get('amount', 'N/A')),
            network=data['network'],
            wallet_address=data.get('wallet_address', data.get('target_address', 'N/A')),
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
        
        # Обновляем контактные данные в основной таблице транзакций
        change_param = f"{str(data.get('contact', ''))}/{message.from_user.username or ''}"
        google_update_params = {
            "contact": [change_param, 9]
        }
        success = update_transaction_status(data['transaction_hash'], google_update_params)

        await state.clear()

async def update_pin_session_with_amount(user_id: int, pin_code: str, amount: float):
    """Обновляет сессию PIN-кода с суммой транзакции"""
    try:
        if not redis_client:
            return False
            
        # Находим сессию по PIN-коду
        pin_key = f"pin_session:{user_id}:{pin_code}"
        session_id = redis_client.get(pin_key)
        
        if session_id:
            # Получаем данные сессии
            session_data_str = redis_client.get(session_id)
            if session_data_str:
                session_data = json.loads(session_data_str)
                session_data['amount'] = amount
                
                # Обновляем сессию
                redis_client.setex(session_id, 7200, json.dumps(session_data))
                logger.info(f"Сессия PIN-кода обновлена с суммой {amount} для пользователя {user_id}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления сессии PIN с суммой: {e}")
        return False

# Регистрация хендлеров
def register_crypto_handlers(dp: Dispatcher):
    dp.message.register(start_crypto, Command("crypto"))
    dp.message.register(set_crypto_operation, StateFilter(CryptoFSM.operation))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    # dp.message.register(generate_pin, StateFilter(CryptoFSM.pin_generation))  # УБИРАЕМ
    dp.message.register(verify_pin, StateFilter(CryptoFSM.pin_verification))
    dp.message.register(get_client_name, StateFilter(CryptoFSM.client_name))
    dp.message.register(get_client_wallet, StateFilter(CryptoFSM.client_wallet))
    dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))
