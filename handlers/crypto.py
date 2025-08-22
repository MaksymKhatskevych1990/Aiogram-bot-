from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton




from google_utils import get_wallet_address, save_transaction_hash, verify_transaction, update_transaction_status
from utils.validators import is_valid_tx_hash
from utils.extract_hash_in_url import extract_tx_hash
from keyboards import get_network_keyboard_with_back, get_back_keyboard, get_crypto_operation_keyboard, get_action_keyboard
from utils.generate_qr_code import generate_wallet_qr
from utils.commission_calculator import commission_calculator
from localization import get_message

from config import logger

WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"
# Состояния FSM
class CryptoFSM(StatesGroup):
    operation = State()  # Купить USDT / Продать USDT
    network = State()
    amount = State()
    client_wallet = State()  # для режима "Купить USDT"
    transaction_hash = State()  # для режима "Продать USDT"
    client_name = State()  # для режима "Купить USDT" - имя пользователя
    contact = State()
    verification = State()

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
        else:
            await message.answer(get_message("address_error", operation_data.get("language", "ru")))
    
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
    
    if op == get_message("crypto_buy_usdt", lang):
        # Пользователь хочет купить USDT - вводит желаемую сумму USDT
        # Бот рассчитывает, сколько нужно заплатить в USD
        commission_result = commission_calculator.calculate_commission('USD_to_USDT', amount, exchange_rate)
        
        if commission_result['success']:
            # Формируем примечание о комиссии
            if commission_result['manager_required']:
                commission_note = get_message("commission_manager_required", lang)
            elif commission_result['commission_type'] == 'percentage':
                commission_note = get_message("commission_percentage", lang, percentage=commission_result['commission_value'])
            elif commission_result['commission_type'] == 'fixed':
                commission_note = get_message("commission_fixed", lang, amount=commission_result['commission_value'])
            else:
                commission_note = ""
            
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
                usd_to_pay=commission_result['final_amount']  # сколько USD нужно заплатить
            )
            
            # При покупке USDT сначала спрашиваем имя
            await message.answer(get_message("enter_name", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.client_name)
            
        else:
            await message.answer(f"❌ Ошибка расчета комиссии: {commission_result['error']}")
            
    else:
        # Продажа USDT - пользователь вводит сумму USDT для продажи
        # Бот рассчитывает, сколько USD он получит
        commission_result = commission_calculator.calculate_commission('USDT_to_USD', amount, exchange_rate)
        
        if commission_result['success']:
            # Формируем примечание о комиссии
            if commission_result['manager_required']:
                commission_note = get_message("commission_manager_required", lang)
            elif commission_result['commission_type'] == 'percentage':
                commission_note = get_message("commission_percentage", lang, percentage=commission_result['commission_value'])
            elif commission_result['commission_type'] == 'fixed':
                commission_note = get_message("commission_fixed", lang, amount=commission_result['commission_value'])
            else:
                commission_note = ""
            
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
                usd_to_receive=commission_result['final_amount']  # сколько USD получит
            )
            
            # При продаже USDT показываем инструкцию (адрес уже показан при выборе сети)
            final_amount = f"{commission_result['final_amount']:.2f}"
            await message.answer(
                f"{get_message('sell_instruction_header', lang)}\n\n"
                f"{get_message('sell_instruction_step1', lang, amount=f'{amount:.2f}')}\n"
                f"{get_message('sell_instruction_step2', lang)}\n"
                f"{get_message('sell_instruction_step3', lang)}\n\n"
                f"{get_message('sell_instruction_final', lang, amount=final_amount)}",
                parse_mode="Markdown"
            )
            
            await message.answer(get_message("enter_tx_hash", lang), reply_markup=get_back_keyboard(lang))
            await state.set_state(CryptoFSM.transaction_hash)
        else:
            await message.answer(f"❌ Ошибка расчета комиссии: {commission_result['error']}")

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
    from config import logger, TOKEN

    bot = Bot(token=TOKEN)
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
    dp.message.register(set_crypto_operation, StateFilter(CryptoFSM.operation))
    dp.message.register(get_network, StateFilter(CryptoFSM.network))
    dp.message.register(get_amount, StateFilter(CryptoFSM.amount))
    dp.message.register(get_client_name, StateFilter(CryptoFSM.client_name))
    dp.message.register(get_client_wallet, StateFilter(CryptoFSM.client_wallet))
    dp.message.register(get_transaction_hash, StateFilter(CryptoFSM.transaction_hash))
    dp.message.register(get_contact, StateFilter(CryptoFSM.contact))
