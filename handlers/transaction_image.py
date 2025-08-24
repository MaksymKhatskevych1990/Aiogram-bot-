import os
import tempfile
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile
from aiogram.types import CallbackQuery

from utils.transaction_image_parser import transaction_parser
from utils.validators import is_valid_tx_hash
from google_utils import verify_transaction, save_transaction_hash
from localization import get_message
from keyboards import get_back_keyboard, get_confirm_transaction_keyboard, get_transaction_image_keyboard
import logging

logger = logging.getLogger(__name__)

class TransactionImageFSM(StatesGroup):
    """Состояния для обработки изображения транзакции"""
    waiting_for_image = State()
    confirm_details = State()
    processing = State()

async def start_transaction_image_verification(message: types.Message, state: FSMContext):
    """
    Начинает процесс проверки транзакции по изображению
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    logger.info(f"🔍 start_transaction_image_verification вызвана")
    logger.info(f"🔍 Текущие данные состояния: {data}")
    
    # Проверяем, что сообщение содержит текст перед проверкой кнопок
    if message.text:
        logger.info(f"🔍 Сообщение содержит текст: '{message.text}'")
        # Проверяем кнопки возврата только для текстовых сообщений
        if get_message("back", lang) in message.text:
            logger.info("🔍 Нажата кнопка 'Назад'")
            # Возврат к выбору способа проверки - возвращаемся к состоянию verification
            from handlers.crypto import CryptoFSM
            await state.set_state(CryptoFSM.verification)
            await message.answer(get_message("choose_verification_method", lang), 
                               reply_markup=get_transaction_image_keyboard(lang))
            return
        
        if get_message("back_to_main", lang) in message.text:
            logger.info("🔍 Нажата кнопка 'Назад'")
            # Возврат на главную
            await message.answer(get_message("choose_action", lang), reply_markup=get_back_keyboard(lang))
            from handlers.start import StartFSM
            await state.set_state(StartFSM.action)
            return
    
    # Если это не кнопка возврата или сообщение без текста, начинаем процесс проверки изображения
    # ВАЖНО: Сохраняем текущие данные состояния перед переходом к проверке изображения
    current_data = await state.get_data()
    
    logger.info(f"🔍 Начинаем процесс проверки изображения")
    await message.answer(
        get_message("send_transaction_image", lang),
        reply_markup=get_back_keyboard(lang)
    )
    
    # Переходим к состоянию ожидания изображения, сохраняя все предыдущие данные
    await state.set_state(TransactionImageFSM.waiting_for_image)
    
    # Восстанавливаем данные состояния, если они были потеряны
    if current_data:
        await state.update_data(**current_data)
        logger.info(f"✅ Восстановлены данные состояния: {current_data}")

async def handle_transaction_image(message: types.Message, state: FSMContext):
    """
    Обрабатывает загруженное изображение транзакции
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    logger.info(f"🔍 handle_transaction_image вызвана")
    logger.info(f"🔍 Текущие данные состояния: {data}")
    
    # Проверяем, что это изображение
    if not message.photo:
        logger.warning("⚠️ Сообщение не содержит изображение")
        await message.answer(
            get_message("please_send_image", lang),
            reply_markup=get_back_keyboard(lang)
        )
        return
    
    logger.info(f"✅ Получено изображение, начинаем обработку")
    
    # Получаем файл изображения
    photo = message.photo[-1]  # Берем самое большое изображение
    file_info = await message.bot.get_file(photo.file_id)
    
    await message.answer(get_message("processing_image", lang))
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        # Скачиваем изображение
        await message.bot.download_file(file_info.file_path, temp_path)
        
        # Обрабатываем изображение
        await state.set_state(TransactionImageFSM.processing)
        
        # Извлекаем детали транзакции
        transaction_details = transaction_parser.extract_transaction_details(temp_path)
        
        # Удаляем временный файл
        os.unlink(temp_path)
        
        if not transaction_details['success']:
            await message.answer(
                get_message("failed_to_extract_hash", lang, error=transaction_details.get('error', 'Неизвестная ошибка')),
                reply_markup=get_back_keyboard(lang)
            )
            # ВАЖНО: Возвращаемся к состоянию verification, а не очищаем состояние
            from handlers.crypto import CryptoFSM
            await state.set_state(CryptoFSM.verification)
            await message.answer(get_message("choose_verification_method", lang), 
                               reply_markup=get_transaction_image_keyboard(lang))
            return
        
        # Сохраняем детали в состоянии
        await state.update_data(
            transaction_hash=transaction_details['hash'],
            amount=transaction_details.get('amount'),
            network=transaction_details.get('network'),
            address=transaction_details.get('address'),
            raw_text=transaction_details.get('raw_text')
        )
        
        logger.info(f"✅ Данные сохранены в состоянии: transaction_hash={transaction_details['hash']}")
        
        # Формируем сообщение с деталями
        details_message = get_message("transaction_details_found", lang)
        details_message += f"\n\n🔗 **Хеш транзакции:** `{transaction_details['hash']}`"
        
        if transaction_details.get('amount'):
            details_message += f"\n💰 **Сумма:** {transaction_details['amount']}"
        
        if transaction_details.get('network'):
            details_message += f"\n🌐 **Сеть:** {transaction_details['network']}"
        
        if transaction_details.get('address'):
            details_message += f"\n📮 **Адрес:** `{transaction_details['address']}`"
        
        details_message += f"\n\n{get_message('confirm_transaction_details', lang)}"
        
        # Показываем детали и просим подтверждения через inline кнопки
        await message.answer(
            details_message,
            reply_markup=get_confirm_transaction_keyboard(lang),
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Переходим к состоянию confirm_details")
        await state.set_state(TransactionImageFSM.confirm_details)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке изображения: {e}")
        await message.answer(
            get_message("error_processing_image", lang),
            reply_markup=get_back_keyboard(lang)
        )
        # ВАЖНО: Возвращаемся к состоянию verification, а не очищаем состояние
        from handlers.crypto import CryptoFSM
        await state.set_state(CryptoFSM.verification)
        await message.answer(get_message("choose_verification_method", lang), 
                           reply_markup=get_transaction_image_keyboard(lang))

async def process_confirm_tx(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает подтверждение деталей транзакции через inline кнопку
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    logger.info(f"🔍 process_confirm_tx вызвана")
    logger.info(f"🔍 Текущие данные состояния: {data}")
    
    # Пользователь подтвердил детали
    transaction_hash = data.get('transaction_hash')
    logger.info(f"🔍 Хеш транзакции из состояния: {transaction_hash}")
    
    await callback.message.answer(get_message("verifying_transaction", lang))
    
    try:
        # Проверяем транзакцию через API
        # Получаем адрес кошелька для проверки
        from google_utils import get_wallet_address
        wallet_address = get_wallet_address(data.get('network', 'TRC20'))
        logger.info(f"🔍 Адрес кошелька: {wallet_address}")
        
        if not wallet_address:
            logger.error("❌ Не удалось получить адрес кошелька")
            await callback.message.answer(
                get_message("address_error", lang),
                reply_markup=get_back_keyboard(lang)
            )
            # ВАЖНО: Возвращаемся к состоянию verification, а не очищаем состояние
            from handlers.crypto import CryptoFSM
            await state.set_state(CryptoFSM.verification)
            await callback.message.answer(get_message("choose_verification_method", lang), 
                                       reply_markup=get_transaction_image_keyboard(lang))
            await callback.answer()
            return
        
        logger.info(f"🔍 Начинаем проверку транзакции: {transaction_hash}")
        verification_result = await verify_transaction(
            tx_hash=transaction_hash,
            network=data.get('network', 'TRC20'),
            target_address=wallet_address,
            username=callback.from_user.id,
            chat_id=callback.message.chat.id,
            bot_id=callback.message.bot.id,
            lang=lang
        )
        
        logger.info(f"🔍 Результат проверки: {verification_result}")
        
        if verification_result.get('success'):
            logger.info("✅ Транзакция успешно проверена!")
            # Сохраняем транзакцию
            google_params = [
                transaction_hash,
                data.get('amount', ''),
                data.get('network', ''),
                data.get('address', ''),
                '',  # timestamp (будет заполнен позже)
                'pending',  # status
                '',  # amount (будет заполнен позже)
                ''   # error
            ]
            
            save_transaction_hash(google_params)
            
            await callback.message.answer(
                get_message("transaction_verified_success", lang),
                reply_markup=get_back_keyboard(lang)
            )
            
            # ВАЖНО: После успешной проверки возвращаемся к главному меню
            await callback.message.answer(get_message("choose_action", lang), reply_markup=get_back_keyboard(lang))
            from handlers.start import StartFSM
            await state.set_state(StartFSM.action)
        else:
            logger.warning(f"⚠️ Проверка транзакции не удалась: {verification_result}")
            await callback.message.answer(
                get_message("transaction_verification_failed", lang, error=verification_result.get('error', 'Неизвестная ошибка')),
                reply_markup=get_back_keyboard(lang)
            )
            # ВАЖНО: Возвращаемся к состоянию verification при ошибке
            from handlers.crypto import CryptoFSM
            await state.set_state(CryptoFSM.verification)
            await callback.message.answer(get_message("choose_verification_method", lang), 
                                       reply_markup=get_transaction_image_keyboard(lang))
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке транзакции: {e}")
        await callback.message.answer(
            get_message("error_verifying_transaction", lang),
            reply_markup=get_back_keyboard(lang)
        )
        # ВАЖНО: Возвращаемся к состоянию verification при ошибке
        from handlers.crypto import CryptoFSM
        await state.set_state(CryptoFSM.verification)
        await callback.message.answer(get_message("choose_verification_method", lang), 
                                   reply_markup=get_transaction_image_keyboard(lang))
    
    await callback.answer()

async def process_cancel_tx(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену деталей транзакции через inline кнопку
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    logger.info("❌ Кнопка отмены нажата")
    
    # Пользователь отменил
    await callback.message.answer(
        get_message("transaction_cancelled", lang),
        reply_markup=get_back_keyboard(lang)
    )
    
    # ВАЖНО: Возвращаемся к состоянию verification при отмене
    from handlers.crypto import CryptoFSM
    await state.set_state(CryptoFSM.verification)
    await callback.message.answer(get_message("choose_verification_method", lang), 
                               reply_markup=get_transaction_image_keyboard(lang))
    
    await callback.answer()

async def handle_back_from_image_verification(message: types.Message, state: FSMContext):
    """
    Обрабатывает возврат из процесса проверки изображения
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # ВАЖНО: Возвращаемся к состоянию verification, а не очищаем состояние
    from handlers.crypto import CryptoFSM
    await state.set_state(CryptoFSM.verification)
    await message.answer(
        get_message("choose_verification_method", lang),
        reply_markup=get_transaction_image_keyboard(lang)
    )

def register_transaction_image_handlers(dp: Dispatcher):
    """Регистрирует хендлеры для проверки транзакций по изображению"""

    from handlers.crypto import CryptoFSM  # импортим тут, чтобы избежать циклических импортов

    # 🔹 Старт процесса проверки по изображению (выбор пользователем этого метода)
    dp.message.register(
        start_transaction_image_verification,
        StateFilter(CryptoFSM.verification),
        lambda msg: msg.text and get_message("image_verification", msg.from_user.language_code or "ru") in msg.text
    )

    # 🔹 Обработка загруженного изображения (ждем фото)
    dp.message.register(
        handle_transaction_image,
        StateFilter(TransactionImageFSM.waiting_for_image),
        lambda msg: msg.photo is not None
    )

    # 🔹 Подтверждение или отмена найденных деталей через inline кнопки
    dp.callback_query.register(
        process_confirm_tx,
        F.data == "confirm_tx",
        StateFilter(TransactionImageFSM.confirm_details)
    )
    dp.callback_query.register(
        process_cancel_tx,
        F.data == "cancel_tx",
        StateFilter(TransactionImageFSM.confirm_details)
    )

    # 🔹 Возврат назад (универсальный хендлер для кнопок "Назад" и "На главную")
    dp.message.register(
        handle_back_from_image_verification,
        StateFilter(TransactionImageFSM.waiting_for_image, TransactionImageFSM.confirm_details),
        lambda msg: msg.text and (
            get_message("back", msg.from_user.language_code or "ru") in msg.text
            or get_message("back_to_main", msg.from_user.language_code or "ru") in msg.text
        )
    )