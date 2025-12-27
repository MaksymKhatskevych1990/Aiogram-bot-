from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime




# Функции для работы с блокчейном теперь в networks модулях
# Синхронные обертки больше не используются - используем async версии напрямую
# from utils.backend_utils import (
#     is_duplicate_transaction,
#     update_transaction_status,
#     is_pin_exists,
#     update_pin_phone
# )  # Используем API вместо Google Sheets
from utils.validators import is_valid_tx_hash, is_valid_wallet_address
from utils.extract_hash_in_url import extract_tx_hash
from keyboards import get_network_keyboard_with_back, get_back_keyboard, get_crypto_operation_keyboard, get_action_keyboard
from utils.generate_qr_code import generate_wallet_qr
from utils.commission_calculator import commission_calculator
from utils.api_client import get_api_client, BackendAPIError
from config import logger, get_current_bot_token
from localization import get_message

WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"
# Состояния FSM
class CryptoFSM(StatesGroup):
    operation = State()  # Купить USDT / Продать USDT
    network = State()
    amount = State()
    client_wallet = State()  # для режима "Купить USDT"
    # transaction_hash = State()  # для режима "Продать USDT" (СТАРОЕ - будет удалено)
    client_name = State()  # для режима "Купить USDT" - имя пользователя
    contact = State()
    verification = State()
    
    # НОВЫЕ СОСТОЯНИЯ ДЛЯ PIN-СИСТЕМЫ
    user_wallet = State()      # Ввод кошелька пользователя для продажи USDT
    pin_generated = State()    # PIN сгенерирован, ожидание перевода
    phone_input = State()      # Ввод номера телефона

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
    # if operation == get_message("crypto_sell_usdt", operation_data.get("language", "ru")):
    #     wallet_address = get_wallet_address(message.text)
    #     await state.update_data(wallet_address=wallet_address)
        
    #     if wallet_address:
    #         logo_path = "img/logo-qr.png"
    #         await message.answer(
    #             get_message("send_to_address", operation_data.get("language", "ru"), wallet_address=wallet_address, network=message.text),
    #             parse_mode="Markdown"
    #         )
    #         await generate_wallet_qr(message.bot, message.chat.id, wallet_address, message.text, logo_path, operation_data.get("language", "ru"))
    #     else:
    #         await message.answer(get_message("address_error", operation_data.get("language", "ru")))
    
    await message.answer(get_message("enter_amount", operation_data.get("language", "ru")), reply_markup=get_back_keyboard(operation_data.get("language", "ru")))
    await state.set_state(CryptoFSM.amount)

# Ввод суммы
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
    
    # Определяем режим операции
    op = (data.get('operation') or '').strip()
    exchange_rate = commission_calculator.get_exchange_rate()
    
    # Пытаемся получить комиссию из backend API
    bot_token = get_current_bot_token()
    api_client = get_api_client()
    commission_result = None
    
    try:
        if op == get_message("crypto_buy_usdt", lang):
            # Пользователь хочет купить USDT - вводит желаемую сумму USDT
            direction = "USD_to_USDT"
        else:
            # Продажа USDT
            direction = "USDT_to_USD"
        
        if bot_token:
            logger.info(f"Запрос комиссии через API: direction={direction}, amount={amount}, bot_token={bot_token[:10]}...")
            api_result = await api_client.calculate_commission(bot_token, direction, amount)
            
            # Преобразуем ответ API в формат, совместимый с локальным калькулятором
            commission_result = {
                'success': True,
                'operation_type': direction,
                'original_amount': api_result.get('amount_in', amount),
                'commission_amount': api_result.get('commission', 0),
                'final_amount': api_result.get('amount_out', amount),
                'commission_type': api_result.get('commission_type', 'fixed'),
                'commission_value': api_result.get('commission_value', 0),
                'manager_required': False,
                'rate_used': exchange_rate,
                'rule_found': api_result.get('rule_found', False)
            }
            logger.info(f"✅ Комиссия получена из API: commission={commission_result['commission_amount']}, final_amount={commission_result['final_amount']}")
        else:
            logger.warning("Токен бота не найден, используем локальный калькулятор")
            raise BackendAPIError("Bot token not found")
            
    except (BackendAPIError, Exception) as e:
        logger.warning(f"⚠️ Ошибка получения комиссии из API: {e}, используем локальный калькулятор")
        # Fallback на локальный калькулятор
        if op == get_message("crypto_buy_usdt", lang):
            commission_result = commission_calculator.calculate_commission('USD_to_USDT', amount, exchange_rate)
        else:
            commission_result = commission_calculator.calculate_commission('USDT_to_USD', amount, exchange_rate)
    
    if commission_result and commission_result.get('success'):
        # Формируем примечание о комиссии
        if commission_result.get('manager_required'):
            commission_note = get_message("commission_manager_required", lang)
        elif commission_result.get('commission_type') == 'percentage':
            commission_note = get_message("commission_percentage", lang, percentage=commission_result.get('commission_value', 0))
        elif commission_result.get('commission_type') == 'fixed':
            commission_note = get_message("commission_fixed", lang, amount=commission_result.get('commission_value', 0))
        else:
            commission_note = ""
        
        if op == get_message("crypto_buy_usdt", lang):
            # Показываем расчет: сколько USDT получит и сколько USD нужно заплатить
            await message.answer(
                f" *Расчет покупки USDT*\n\n"
                f"🎯 Желаемая сумма: {amount:.2f} USDT\n"
                f"💱 Курс обмена: {exchange_rate or 'Не указан'} USD/USDT\n"
                f"💸 Комиссия: {commission_result['commission_amount']:.2f} USD\n"
                f"💵 К оплате: {commission_result['final_amount']:.2f} USD\n\n"
                f"{commission_note}",
                parse_mode="Markdown"
            )
            
            # Сохраняем результат расчета
            await state.update_data(
                usdt_amount=amount,  # сколько USDT хочет купить
                usd_to_pay=commission_result['final_amount'],  # сколько USD нужно заплатить
                commission_amount=commission_result['commission_amount'],  # размер комиссии
                commission_type=commission_result.get('commission_type', 'fixed')  # тип комиссии
            )
            
            # При покупке USDT сначала спрашиваем имя
            await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.client_name)
        else:
            # Показываем расчет: сколько USDT продает и сколько USD получит
            await message.answer(
                f" *Расчет продажи USDT*\n\n"
                f" Сумма к продаже: {amount:.2f} USDT\n"
                f"💱 Курс обмена: {exchange_rate or 'Не указан'} USD/USDT\n"
                f"💸 Комиссия: {commission_result['commission_amount']:.2f} USD\n"
                f"💵 К получению: {commission_result['final_amount']:.2f} USD\n\n"
                f"{commission_note}",
                parse_mode="Markdown"
            )
            
            # Сохраняем результат расчета
            await state.update_data(
                usdt_amount=amount,  # сколько USDT продает
                usd_to_receive=commission_result['final_amount'],  # сколько USD получит
                commission_amount=commission_result['commission_amount'],  # размер комиссии
                commission_type=commission_result.get('commission_type', 'fixed')  # тип комиссии
            )
            
            # НОВАЯ ЛОГИКА: При продаже USDT запрашиваем кошелек пользователя
            await message.answer(
                get_message("enter_user_wallet", lang),
                reply_markup=get_back_keyboard(lang)
            )
            await state.set_state(CryptoFSM.user_wallet)
    else:
        error_msg = commission_result.get('error', 'Неизвестная ошибка') if commission_result else 'Ошибка расчета комиссии'
        await message.answer(f"❌ Ошибка расчета комиссии: {error_msg}")

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
    
    user_id = message.from_user.id
    chat_id = message.chat.id  
    me = await message.bot.get_me()
    bot_id = me.id 

    user_input = message.text.strip()
    tx_hash = extract_tx_hash(user_input) #Проверка хэша на валидность
    if not tx_hash:
        await message.answer(get_message("invalid_tx_hash", lang))
        return
    
    # Используем async версию
    from utils.backend_utils import is_duplicate_transaction_async
    if await is_duplicate_transaction_async(tx_hash):
            await message.answer(get_message("is_duplicate_transaction", lang))
            return

    await state.update_data(transaction_hash=tx_hash)
    await message.answer(get_message("checking_tx", lang))
    data = await state.get_data()
    network = data.get('network')
    logger.info("Получен нетворк: %s", network)
    # Получаем адрес кошелька бота из базы данных
    from google_utils import get_wallet_address_from_backend
    from config import get_current_bot_token
    wallet_address = await get_wallet_address_from_backend(network, get_current_bot_token())
    if not is_valid_tx_hash(tx_hash, network): #еще одна проверка хэша на валидность
        await message.answer(get_message("invalid_tx_format", lang))
        return
    from google_utils import verify_transaction
    verification_result = await verify_transaction(
        tx_hash, 
        network, 
        wallet_address,
        int(user_id),
        int(chat_id),
        int(bot_id),
        lang
    )
    
    # # Обрабатываем результат верификации
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

async def send_telegram_notification(chat_id: str, msg):
    from aiogram import Bot
    from config import logger, get_current_bot_token

    bot = Bot(token=get_current_bot_token())
    """
    Отправляет уведомление в Telegram пользователю о подтвержденной транзакции
    """
    
    try:        
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
            # Возврат к вводу хеша для продажи
            await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.transaction_hash)
        return
    
    await state.update_data(contact=message.text)
    
    if op == get_message("crypto_buy_usdt", lang):
        # Для покупки USDT - показываем итоговую информацию и отправляем администратору
        commission = data.get('commission_amount', 0)
        commission_str = f"💸 Комиссия: {commission:.2f} USD\n" if commission > 0 else ""
        
        summary = (
            f"🟢 *Новая заявка: Купить USDT*\n\n"
            f"👤 Имя: {data.get('client_name', 'Не указано')}\n"
            f"🌐 Сеть: {data.get('network', '')}\n"
            f"🎯 Желаемая сумма: {data.get('usdt_amount', '')} USDT\n"
            f"{commission_str}"
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
            f"🎯 Сумма к покупке: {data.get('usdt_amount', '')} USDT\n"
            f"{commission_str}"
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
        summary = get_message(
            "crypto_request_summary", lang,
            amount=data.get('amount_result', data.get('amount', 'N/A')),
            network=data['network'],
            wallet_address=data['target_address'],
            tx_hash=data['transaction_hash'],
            contact=data['contact'],
            username=message.from_user.username if message.from_user.username else 'N/A'
        )
        from config import ADMIN_CHAT_ID
        await message.bot.send_message(ADMIN_CHAT_ID, summary)
        await message.answer(
            get_message("crypto_request_success", lang, summary=summary)
        )
        logger.debug(f"Отправляю сообщение администратору в чат: {ADMIN_CHAT_ID}")
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

        # Обновляем статус транзакции через backend API
        from utils.backend_utils import update_transaction_status_async
        success = await update_transaction_status_async(data['transaction_hash'], "completed")
        # if not success:
        #     await message.answer(get_message("google_sheet_error", lang))

        await state.clear()

# =============================================================================
# НОВЫЕ ОБРАБОТЧИКИ ДЛЯ PIN-СИСТЕМЫ
# =============================================================================

# Обработчик ввода кошелька пользователя
async def get_user_wallet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # Проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        await message.answer(get_message("enter_amount", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(CryptoFSM.amount)
        return
    
    user_wallet = message.text.strip()
    network = data.get('network')
    
    # Валидация кошелька
    if not is_valid_wallet_address(user_wallet, network):
        await message.answer(
            get_message("invalid_wallet_format", lang, network=network),
            reply_markup=get_back_keyboard(lang)
        )
        return
    
    # Получаем адрес кошелька бота из базы данных (адрес для приема платежей)
    from google_utils import get_wallet_address_from_backend
    from config import get_current_bot_token
    bot_wallet = await get_wallet_address_from_backend(network, get_current_bot_token())
    
    # Нормализуем адреса для сравнения (убираем пробелы, приводим к нижнему регистру)
    user_wallet_normalized = user_wallet.strip().lower()
    
    # Проверяем, что пользователь не ввел адрес бота (адрес для приема платежей)
    # Примечание: Для тестирования владелец бота может использовать свой адрес,
    # поэтому проверка не блокирует процесс, а только логирует
    if bot_wallet and bot_wallet.strip():
        bot_wallet_normalized = bot_wallet.strip().lower()
        
        # Детальное логирование для отладки
        logger.info(f"=== ПРОВЕРКА АДРЕСА КОШЕЛЬКА ===")
        logger.info(f"Сеть: {network}")
        logger.info(f"Адрес пользователя: {user_wallet} (длина: {len(user_wallet)})")
        logger.info(f"Адрес бота из БД: {bot_wallet} (длина: {len(bot_wallet)})")
        logger.info(f"Нормализованный адрес пользователя: {user_wallet_normalized}")
        logger.info(f"Нормализованный адрес бота: {bot_wallet_normalized}")
        logger.info(f"Адреса совпадают: {user_wallet_normalized == bot_wallet_normalized}")
        
        if user_wallet_normalized == bot_wallet_normalized:
            # Адрес совпадает с адресом бота - это нормально для тестирования владельцем бота
            logger.info(f"ℹ️ Пользователь {message.from_user.id} ввел адрес, который совпадает с адресом бота в настройках")
            logger.info(f"   Это может быть нормально, если пользователь тестирует бота или является владельцем")
            logger.info(f"   Продолжаем обработку без блокировки")
            # Не блокируем - продолжаем обработку
        else:
            logger.info(f"✅ Адреса разные, продолжаем обработку")
    else:
        # Если адрес бота не настроен, предупреждаем, но продолжаем
        logger.warning(f"Адрес кошелька бота для сети {network} не настроен в базе данных. Продолжаем без проверки.")
    
    # Сохраняем кошелек пользователя и адрес бота
    await state.update_data(user_wallet=user_wallet, bot_wallet=bot_wallet)
    
    # Генерируем PIN-код и сохраняем в таблицу
    # bot_wallet уже получен выше
    amount = data.get('usdt_amount')
    user_id = message.from_user.id
    
    # Генерируем PIN-код (телефон будет добавлен позже)
    # Используем async версию, так как мы в async контексте
    from utils.backend_utils import save_pin_code_async
    pin_code = await save_pin_code_async(
        user_wallet=user_wallet,
        target_wallet=bot_wallet,
        network=network,
        amount=amount,
        phone="",  # Пока пустой, будет заполнен позже
        user_id=user_id,
        chat_id=message.chat.id,  # Добавляем chat_id для уведомлений
        expires_hours=1
    )
    
    if not pin_code:
        await message.answer(
            get_message("pin_generation_error", lang),
            reply_markup=get_back_keyboard(lang)
        )
        return
    
    # Сохраняем PIN-код в состояние
    await state.update_data(pin_code=pin_code)
    
    # Показываем адрес для перевода с PIN-кодом
    await message.answer(
        get_message("send_to_address_with_pin", lang, 
                   wallet_address=bot_wallet, 
                   network=network,
                   pin_code=pin_code,
                   amount=f"{amount:.2f}"),
        parse_mode="Markdown"
    )
    
    # Генерируем QR-код
    logo_path = "img/logo-qr.png"
    await generate_wallet_qr(message.bot, message.chat.id, bot_wallet, network, logo_path, lang)
    
    # Запрашиваем номер телефона
    await message.answer(
        get_message("enter_phone_number", lang),
        reply_markup=get_back_keyboard(lang)
    )
    await state.set_state(CryptoFSM.phone_input)

# Обработчик ввода номера телефона
async def get_phone_number(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # Проверяем кнопку "Вернуться на главную"
    if get_message("back_to_main", lang) in message.text:
        await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    if get_message("back", lang) in message.text:
        # Возврат к вводу кошелька
        await message.answer(
            get_message("enter_user_wallet", lang),
            reply_markup=get_back_keyboard(lang)
        )
        await state.set_state(CryptoFSM.user_wallet)
        return
    
    phone = message.text.strip()
    
    # Сохраняем номер телефона
    await state.update_data(phone=phone)
    
    # Обновляем PIN-код в таблице с номером телефона
    pin_code = data.get('pin_code')
    network = data.get('network', 'TRC20')
    if pin_code:
        # Используем async версию
        from utils.backend_utils import update_pin_phone_async
        await update_pin_phone_async(pin_code, phone, network)
    
    # Показываем финальную инструкцию
    # Получаем адрес кошелька бота
    from google_utils import get_wallet_address_from_backend
    from config import get_current_bot_token
    bot_wallet_for_instructions = await get_wallet_address_from_backend(data.get('network', ''), get_current_bot_token())
    
    # Формируем сообщение с комиссией
    commission = data.get('commission_amount', 0)
    commission_info = ""
    if commission > 0:
        commission_info = f"💸 Комиссия: {commission:.2f} USD\n"
    
    # Получаем базовое сообщение и добавляем комиссию
    base_message = get_message("transaction_instructions", lang,
                              pin_code=pin_code,
                              amount=f"{data.get('usdt_amount', 0):.2f}",
                              network=data.get('network', ''),
                              wallet_address=bot_wallet_for_instructions or '')
    
    # Добавляем информацию о комиссии и сумме к получению
    usd_to_receive = data.get('usd_to_receive', 0)
    if usd_to_receive > 0:
        full_message = (
            f"{base_message}\n\n"
            f"{commission_info}"
            f"💵 К получению: {usd_to_receive:.2f} USD"
        )
    else:
        full_message = base_message
    
    await message.answer(full_message, parse_mode="Markdown")
    
    # Отправляем заявку администратору
    await send_admin_notification(message, data, pin_code)
    
    # Показываем подтверждение пользователю
    await message.answer(
        get_message("transaction_submitted", lang),
        reply_markup=get_back_keyboard(lang)
    )
    
    # Возвращаемся в главное меню
    await message.answer(get_message("choose_action", lang), reply_markup=get_action_keyboard(lang))
    from handlers.start import StartFSM
    await state.set_state(StartFSM.action)

# Отправка уведомления администратору
async def send_admin_notification(message: types.Message, data: dict, pin_code: str):
    """Отправляет заявку администратору с полными данными"""
    try:
        commission = data.get('commission_amount', 0)
        commission_str = f"💸 Комиссия: {commission:.2f} USD\n" if commission > 0 else ""
        
        summary = (
            f"🟢 *Новая заявка: Продать USDT*\n\n"
            f"👤 Пользователь: @{message.from_user.username if message.from_user.username else 'N/A'}\n"
            f"🌐 Сеть: {data.get('network', '')}\n"
            f"💰 Сумма к продаже: {data.get('usdt_amount', '')} USDT\n"
            f"{commission_str}"
            f"💵 К получению: {data.get('usd_to_receive', '')} USD\n"
            f"🏦 Кошелек пользователя: `{data.get('user_wallet', '')}`\n"
            f"📱 Телефон: {data.get('phone', '')}\n"
            f"🔑 PIN-код: `{pin_code}`\n"
            f"🎯 Адрес для перевода: `{data.get('bot_wallet', 'Не настроен')}`\n"
            f"⏰ Время создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        from config import ADMIN_CHAT_ID
        await message.bot.send_message(ADMIN_CHAT_ID, summary, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

# Регистрация хендлеров
def register_crypto_handlers(dp: Dispatcher):
    dp.message.register(start_crypto, Command("crypto"))
    dp.message.register(set_crypto_operation, StateFilter(CryptoFSM.operation))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    dp.message.register(get_client_name, StateFilter(CryptoFSM.client_name))
    dp.message.register(get_client_wallet, StateFilter(CryptoFSM.client_wallet))
    # dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))
    
    # НОВЫЕ ХЕНДЛЕРЫ ДЛЯ PIN-СИСТЕМЫ
    dp.message.register(get_user_wallet, StateFilter(CryptoFSM.user_wallet))
    dp.message.register(get_phone_number, StateFilter(CryptoFSM.phone_input))
