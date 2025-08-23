import os
import tempfile
from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile

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
    
    # Проверяем кнопки возврата
    if get_message("back", lang) in message.text:
        # Возврат к выбору способа проверки - возвращаемся к состоянию verification
        from handlers.crypto import CryptoFSM
        await state.set_state(CryptoFSM.verification)
        await message.answer(get_message("choose_verification_method", lang), 
                           reply_markup=get_transaction_image_keyboard(lang))
        return
    
    if get_message("back_to_main", lang) in message.text:
        # Возврат на главную
        await message.answer(get_message("choose_action", lang), reply_markup=get_back_keyboard(lang))
        from handlers.start import StartFSM
        await state.set_state(StartFSM.action)
        return
    
    await message.answer(
        get_message("send_transaction_image", lang),
        reply_markup=get_back_keyboard(lang)
    )
    await state.set_state(TransactionImageFSM.waiting_for_image)

async def handle_transaction_image(message: types.Message, state: FSMContext):
    """
    Обрабатывает загруженное изображение транзакции
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    # Проверяем, что это изображение
    if not message.photo:
        await message.answer(
            get_message("please_send_image", lang),
            reply_markup=get_back_keyboard(lang)
        )
        return
    
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
            await state.clear()
            return
        
        # Сохраняем детали в состоянии
        await state.update_data(
            transaction_hash=transaction_details['hash'],
            amount=transaction_details.get('amount'),
            network=transaction_details.get('network'),
            address=transaction_details.get('address'),
            raw_text=transaction_details.get('raw_text')
        )
        
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
        
        # Показываем детали и просим подтверждения
        await message.answer(
            details_message,
            reply_markup=get_confirm_transaction_keyboard(lang),
            parse_mode="Markdown"
        )
        
        await state.set_state(TransactionImageFSM.confirm_details)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке изображения: {e}")
        await message.answer(
            get_message("error_processing_image", lang),
            reply_markup=get_back_keyboard(lang)
        )
        await state.clear()

async def confirm_transaction_details(message: types.Message, state: FSMContext):
    """
    Обрабатывает подтверждение деталей транзакции
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    if message.text == get_message("confirm", lang):
        # Пользователь подтвердил детали
        transaction_hash = data.get('transaction_hash')
        
        await message.answer(get_message("verifying_transaction", lang))
        
        try:
            # Проверяем транзакцию через API
            # Получаем адрес кошелька для проверки
            from google_utils import get_wallet_address
            wallet_address = get_wallet_address(data.get('network', 'TRC20'))
            
            if not wallet_address:
                await message.answer(
                    get_message("address_error", lang),
                    reply_markup=get_back_keyboard(lang)
                )
                await state.clear()
                return
            
            verification_result = await verify_transaction(
                tx_hash=transaction_hash,
                network=data.get('network', 'TRC20'),
                target_address=wallet_address,
                username=message.from_user.id,
                chat_id=message.chat.id,
                bot_id=message.bot.id,
                lang=lang
            )
            
            if verification_result.get('success'):
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
                
                await message.answer(
                    get_message("transaction_verified_success", lang),
                    reply_markup=get_back_keyboard(lang)
                )
            else:
                await message.answer(
                    get_message("transaction_verification_failed", lang, error=verification_result.get('error', 'Неизвестная ошибка')),
                    reply_markup=get_back_keyboard(lang)
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке транзакции: {e}")
            await message.answer(
                get_message("error_verifying_transaction", lang),
                reply_markup=get_back_keyboard(lang)
            )
        
        await state.clear()
        
    elif message.text == get_message("cancel", lang):
        # Пользователь отменил
        await message.answer(
            get_message("transaction_cancelled", lang),
            reply_markup=get_back_keyboard(lang)
        )
        await state.clear()
        
    else:
        # Неизвестная команда
        await message.answer(
            get_message("please_confirm_or_cancel", lang),
            reply_markup=get_confirm_transaction_keyboard(lang)
        )

async def handle_back_from_image_verification(message: types.Message, state: FSMContext):
    """
    Обрабатывает возврат из процесса проверки изображения
    """
    data = await state.get_data()
    lang = data.get("language", "ru")
    
    await message.answer(
        get_message("choose_action", lang),
        reply_markup=get_back_keyboard(lang)
    )
    await state.clear()

def register_transaction_image_handlers(dp: Dispatcher):
    """Регистрирует хендлеры для обработки изображений транзакций"""
    
    # Хендлер для начала процесса (когда пользователь выбирает проверку по изображению)
    dp.message.register(
        start_transaction_image_verification,
        StateFilter(TransactionImageFSM.waiting_for_image)
    )
    
    # Хендлер для изображений (только когда есть фото)
    dp.message.register(
        handle_transaction_image,
        StateFilter(TransactionImageFSM.waiting_for_image),
        lambda msg: msg.photo is not None
    )
    
    # Хендлер для подтверждения деталей
    dp.message.register(
        confirm_transaction_details,
        StateFilter(TransactionImageFSM.confirm_details)
    )
    
    # Хендлер для возврата (только для текстовых сообщений с кнопками возврата)
    dp.message.register(
        handle_back_from_image_verification,
        StateFilter(TransactionImageFSM.waiting_for_image, TransactionImageFSM.confirm_details),
        lambda msg: msg.text and (get_message("back", msg.from_user.language_code or "ru") in msg.text or 
                                 get_message("back_to_main", msg.from_user.language_code or "ru") in msg.text)
    ) 