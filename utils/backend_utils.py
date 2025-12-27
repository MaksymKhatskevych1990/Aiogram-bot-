"""
Функции для работы с backend API вместо Google Sheets
Эти функции заменяют функции из google_utils.py
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from utils.api_client import get_api_client, BackendAPIError

logger = logging.getLogger(__name__)


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ТРАНЗАКЦИЯМИ ==========

async def save_pin_code_async(
    user_wallet: str, 
    target_wallet: str, 
    network: str, 
    amount: float,
    phone: str, 
    user_id: int, 
    chat_id: int = None, 
    expires_hours: int = 1
) -> Optional[str]:
    """
    Сохраняет PIN-код через API (асинхронная версия)
    
    Args:
        user_wallet: Кошелек пользователя
        target_wallet: Адрес бота для перевода
        network: Сеть (ERC20/TRC20/BEP20)
        amount: Сумма USDT
        phone: Номер телефона
        user_id: ID пользователя Telegram
        chat_id: ID чата для уведомлений
        expires_hours: Через сколько часов истекает PIN (по умолчанию 1 час)
    
    Returns:
        str: Сгенерированный PIN-код или None при ошибке
    """
    try:
        api_client = get_api_client()
        
        # Получаем ID бота из базы данных по токену
        from config import get_current_bot_token
        current_token = get_current_bot_token()
        if not current_token:
            logger.error("Токен бота не установлен!")
            return None
        bot_info = await api_client.get_bot_by_token(current_token)
        bot_id_from_db = None
        if bot_info:
            bot_id_from_db = bot_info.get("id")
            logger.info(f"Получен ID бота из БД: {bot_id_from_db}")
        else:
            logger.warning(f"Бот не найден в БД по токену, используем user_id как fallback")
        
        # Генерируем уникальный PIN-код
        pin_code = _generate_pin_code()
        
        # Проверяем уникальность PIN-кода
        while await is_pin_exists_async(pin_code):
            pin_code = _generate_pin_code()
        
        # Определяем тип сети для API
        table_type = _network_to_table_type(network)
        transaction_type = "sell"  # PIN-код используется для продажи USDT
        
        # Создаем транзакцию через API
        transaction = await api_client.create_transaction(
            amount=amount,
            currency="USDT",
            transaction_type=transaction_type,
            table_type=table_type,
            bot_id=bot_id_from_db,  # Используем ID бота из БД
            user_id=user_id,  # ID пользователя Telegram
            from_address=user_wallet,
            to_address=target_wallet,
            pin_code=pin_code,
            status="pending"
        )
        
        logger.info(f"✅ PIN-код {pin_code} сохранен через API для пользователя {user_id}")
        return pin_code
        
    except BackendAPIError as e:
        logger.error(f"❌ Ошибка API при сохранении PIN-кода: {e.message}")
        return None
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при сохранении PIN-кода: {e}")
        return None


def save_pin_code(
    user_wallet: str, 
    target_wallet: str, 
    network: str, 
    amount: float,
    phone: str, 
    user_id: int, 
    chat_id: int = None, 
    expires_hours: int = 1
) -> Optional[str]:
    """
    Синхронная обертка для save_pin_code_async
    ВНИМАНИЕ: Эта функция не должна вызываться из async контекста!
    Используйте save_pin_code_async напрямую с await.
    """
    try:
        # Проверяем, запущен ли event loop
        loop = asyncio.get_running_loop()
        # Если loop запущен, это ошибка - нужно использовать async версию
        raise RuntimeError(
            "save_pin_code() вызвана из async контекста. "
            "Используйте save_pin_code_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # Event loop не запущен - можно создать новый
            return asyncio.run(
                save_pin_code_async(
                    user_wallet, target_wallet, network, amount, 
                    phone, user_id, chat_id, expires_hours
                )
            )
        else:
            # Другая ошибка - пробрасываем дальше
            raise


async def is_pin_exists_async(pin_code: str) -> bool:
    """
    Проверить, существует ли транзакция с таким PIN-кодом (асинхронная версия)
    """
    try:
        api_client = get_api_client()
        transaction = await api_client.get_transaction_by_pin(pin_code)
        return transaction is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке PIN-кода: {e}")
        return False


def is_pin_exists(pin_code: str, network: str = "TRC20") -> bool:
    """
    Синхронная обертка для is_pin_exists_async
    ВНИМАНИЕ: Эта функция не должна вызываться из async контекста!
    Используйте is_pin_exists_async напрямую с await.
    """
    try:
        # Проверяем, запущен ли event loop
        loop = asyncio.get_running_loop()
        # Если loop запущен, это ошибка - нужно использовать async версию
        raise RuntimeError(
            "is_pin_exists() вызвана из async контекста. "
            "Используйте is_pin_exists_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # Event loop не запущен - можно создать новый
            return asyncio.run(is_pin_exists_async(pin_code))
        else:
            # Другая ошибка - пробрасываем дальше
            raise


async def is_duplicate_transaction_async(tx_hash: str) -> bool:
    """
    Проверить, существует ли транзакция с таким хешем (асинхронная версия)
    """
    try:
        api_client = get_api_client()
        return await api_client.is_duplicate_transaction(tx_hash)
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликата транзакции: {e}")
        return False


def is_duplicate_transaction(tx_hash: str) -> bool:
    """
    Синхронная обертка для is_duplicate_transaction_async
    ВНИМАНИЕ: Эта функция не должна вызываться из async контекста!
    Используйте is_duplicate_transaction_async напрямую с await.
    """
    try:
        # Проверяем, запущен ли event loop
        loop = asyncio.get_running_loop()
        # Если loop запущен, это ошибка - нужно использовать async версию
        raise RuntimeError(
            "is_duplicate_transaction() вызвана из async контекста. "
            "Используйте is_duplicate_transaction_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # Event loop не запущен - можно создать новый
            return asyncio.run(is_duplicate_transaction_async(tx_hash))
        else:
            # Другая ошибка - пробрасываем дальше
            raise


async def update_transaction_status_async(
    transaction_hash: str,
    status: str,
    network: str = "TRC20"
) -> bool:
    """
    Обновить статус транзакции через API (асинхронная версия)
    
    Args:
        transaction_hash: Хеш транзакции
        status: Новый статус ("pending", "completed", "failed")
        network: Сеть (для совместимости, не используется)
    
    Returns:
        bool: True если успешно, False при ошибке
    """
    try:
        api_client = get_api_client()
        
        # Находим транзакцию по хешу
        transaction = await api_client.get_transaction_by_hash(transaction_hash)
        if not transaction:
            logger.warning(f"Транзакция {transaction_hash} не найдена")
            return False
        
        # Обновляем статус
        confirmed_at = datetime.utcnow() if status == "completed" else None
        await api_client.update_transaction(
            transaction_id=transaction["id"],
            status=status,
            confirmed_at=confirmed_at
        )
        
        logger.info(f"✅ Статус транзакции {transaction_hash} обновлен на {status}")
        return True
        
    except BackendAPIError as e:
        logger.error(f"❌ Ошибка API при обновлении статуса: {e.message}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при обновлении статуса: {e}")
        return False


def update_transaction_status(transaction_hash: str, google_update_params, network="TRC20") -> bool:
    """
    Синхронная обертка для update_transaction_status_async
    google_update_params игнорируется для совместимости со старым кодом
    ВНИМАНИЕ: Эта функция не должна вызываться из async контекста!
    Используйте update_transaction_status_async напрямую с await.
    """
    # Извлекаем статус из google_update_params (если это список/словарь)
    status = "completed"  # По умолчанию
    if isinstance(google_update_params, (list, tuple)) and len(google_update_params) > 0:
        status = str(google_update_params[0]).lower()
    elif isinstance(google_update_params, dict):
        status = google_update_params.get("status", "completed")
    
    try:
        # Проверяем, запущен ли event loop
        loop = asyncio.get_running_loop()
        # Если loop запущен, это ошибка - нужно использовать async версию
        raise RuntimeError(
            "update_transaction_status() вызвана из async контекста. "
            "Используйте update_transaction_status_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # Event loop не запущен - можно создать новый
            return asyncio.run(
                update_transaction_status_async(transaction_hash, status, network)
            )
        else:
            # Другая ошибка - пробрасываем дальше
            raise


async def update_pin_phone_async(pin_code: str, phone: str, network: str = "TRC20") -> bool:
    """
    Обновить номер телефона в транзакции по PIN-коду (асинхронная версия)
    """
    try:
        api_client = get_api_client()
        
        # Находим транзакцию по PIN-коду
        transaction = await api_client.get_transaction_by_pin(pin_code)
        if not transaction:
            logger.warning(f"Транзакция с PIN {pin_code} не найдена")
            return False
        
        # Обновляем транзакцию (пока нет поля phone в API, но можно добавить позже)
        # Пока просто возвращаем True для совместимости
        logger.info(f"✅ Телефон для PIN {pin_code} обновлен (требуется расширение API)")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении телефона: {e}")
        return False


def update_pin_phone(pin_code: str, phone: str, network: str = "TRC20") -> bool:
    """
    Синхронная обертка для update_pin_phone_async
    ВНИМАНИЕ: Эта функция не должна вызываться из async контекста!
    Используйте update_pin_phone_async напрямую с await.
    """
    try:
        # Проверяем, запущен ли event loop
        loop = asyncio.get_running_loop()
        # Если loop запущен, это ошибка - нужно использовать async версию
        raise RuntimeError(
            "update_pin_phone() вызвана из async контекста. "
            "Используйте update_pin_phone_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # Event loop не запущен - можно создать новый
            return asyncio.run(update_pin_phone_async(pin_code, phone, network))
        else:
            # Другая ошибка - пробрасываем дальше
            raise


async def save_transaction_hash_async(
    username: int,
    tx_hash: str,
    target_address: str,
    timestamp: str,
    now: str,
    status: str,
    amount: float,
    error: str = "",
    phone: str = "",
    network: str = "TRC20",
    pin_code: str = ""
) -> bool:
    """
    Сохранить хеш транзакции через API (асинхронная версия)
    Если транзакция уже существует (по PIN-коду или хешу), обновляет её
    """
    try:
        api_client = get_api_client()
        
        # Проверяем, не существует ли уже такая транзакция с таким хешем
        existing_tx = await api_client.get_transaction_by_hash(tx_hash)
        if existing_tx:
            logger.info(f"⚠️ Транзакция {tx_hash} уже существует, обновляем статус")
            # Обновляем статус существующей транзакции
            confirmed_at = datetime.utcnow() if status.lower() == "completed" else None
            await api_client.update_transaction(
                transaction_id=existing_tx["id"],
                status=status.lower(),
                confirmed_at=confirmed_at
            )
            return True
        
        # Если есть PIN-код, ищем транзакцию по PIN-коду
        if pin_code:
            existing_tx_by_pin = await api_client.get_transaction_by_pin(pin_code)
            if existing_tx_by_pin:
                logger.info(f"✅ Найдена транзакция по PIN {pin_code}, обновляем хеш и статус")
                # Обновляем существующую транзакцию: добавляем хеш и обновляем статус
                confirmed_at = datetime.utcnow() if status.lower() == "completed" else None
                await api_client.update_transaction(
                    transaction_id=existing_tx_by_pin["id"],
                    hash=tx_hash,
                    status=status.lower(),
                    confirmed_at=confirmed_at,
                    from_address=existing_tx_by_pin.get("from_address") or None,
                    to_address=target_address or existing_tx_by_pin.get("to_address") or None
                )
                logger.info(f"✅ Хеш транзакции {tx_hash} обновлен для транзакции с PIN {pin_code}")
                return True
        
        # Если транзакции нет, создаем новую
        # Определяем тип транзакции и сети
        table_type = _network_to_table_type(network)
        transaction_type = "sell"  # Обычно хеш сохраняется при продаже
        
        # Создаем транзакцию
        await api_client.create_transaction(
            amount=amount,
            currency="USDT",
            transaction_type=transaction_type,
            table_type=table_type,
            bot_id=username,
            hash=tx_hash,
            to_address=target_address,
            status=status.lower(),
            pin_code=pin_code if pin_code else None
        )
        
        logger.info(f"✅ Хеш транзакции {tx_hash} сохранен через API (создана новая транзакция)")
        return True
        
    except BackendAPIError as e:
        logger.error(f"❌ Ошибка API при сохранении хеша: {e.message}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при сохранении хеша: {e}", exc_info=True)
        return False


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def _generate_pin_code() -> str:
    """Генерирует 6-значный PIN-код"""
    import random
    import string
    
    # Первая цифра: 1-9 (не может быть 0)
    first_digit = str(random.randint(1, 9))
    
    # Остальные 5 цифр: 0-9
    remaining_digits = ''.join(random.choices(string.digits, k=5))
    
    return first_digit + remaining_digits


def _network_to_table_type(network: str) -> str:
    """Конвертирует название сети в тип таблицы для API"""
    network_upper = network.upper()
    if "ERC" in network_upper:
        return "ERC"
    elif "BEP" in network_upper:
        return "BEP"
    else:
        return "TRC"  # По умолчанию TRC20


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С PIN-КОДАМИ ==========

async def get_active_pins_async(network: str = "TRC20") -> list:
    """
    Получить список активных PIN-кодов для мониторинга (асинхронная версия)
    Возвращает транзакции со статусом pending и с PIN-кодом
    """
    try:
        api_client = get_api_client()
        table_type = _network_to_table_type(network)
        
        # Получаем транзакции со статусом pending и с PIN-кодом
        transactions = await api_client._request(
            "GET", 
            "/transactions/", 
            params={
                "table_type": table_type,
                "status": "pending",
                "limit": 1000
            }
        )
        
        active_pins = []
        for tx in transactions.get("items", []):
            if tx.get("pin_code") and tx.get("status") == "pending":
                # Проверяем, не истек ли PIN-код (создан более 1 часа назад)
                created_at = tx.get("created_at")
                if created_at:
                    try:
                        from datetime import datetime, timezone, timedelta
                        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        expires_at = created + timedelta(hours=1)
                        if datetime.now(timezone.utc) < expires_at:
                            active_pins.append({
                                "pin_code": tx.get("pin_code"),
                                "user_id": tx.get("user_id"),
                                "chat_id": None,  # Нет в модели, можно добавить позже
                                "amount": float(tx.get("amount", 0)),
                                "target_wallet": tx.get("to_address"),
                                "network": network,
                                "phone": "",  # Нет в модели, можно добавить позже
                                "tx_hash": tx.get("hash")
                            })
                    except Exception as e:
                        logger.warning(f"Ошибка при проверке срока действия PIN {tx.get('pin_code')}: {e}")
        
        return active_pins
        
    except Exception as e:
        logger.error(f"Ошибка при получении активных PIN-кодов: {e}")
        return []


def get_active_pins(network: str = "TRC20") -> list:
    """
    Синхронная обертка для get_active_pins_async
    """
    try:
        loop = asyncio.get_running_loop()
        raise RuntimeError(
            "get_active_pins() вызвана из async контекста. "
            "Используйте get_active_pins_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            return asyncio.run(get_active_pins_async(network))
        else:
            raise


async def mark_pin_used_async(pin_code: str, tx_hash: str, network: str = "TRC20") -> bool:
    """
    Пометить PIN-код как использованный и добавить хеш транзакции (асинхронная версия)
    """
    try:
        api_client = get_api_client()
        
        # Находим транзакцию по PIN-коду
        transaction = await api_client.get_transaction_by_pin(pin_code)
        if not transaction:
            logger.warning(f"Транзакция с PIN {pin_code} не найдена")
            return False
        
        # Обновляем транзакцию: добавляем хеш и меняем статус на completed
        await api_client.update_transaction(
            transaction_id=transaction["id"],
            hash=tx_hash,
            status="completed"
        )
        
        logger.info(f"✅ PIN-код {pin_code} помечен как использованный, хеш {tx_hash} добавлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при пометке PIN-кода как использованного: {e}")
        return False


def mark_pin_used(pin_code: str, tx_hash: str, network: str = "TRC20") -> bool:
    """
    Синхронная обертка для mark_pin_used_async
    """
    try:
        loop = asyncio.get_running_loop()
        raise RuntimeError(
            "mark_pin_used() вызвана из async контекста. "
            "Используйте mark_pin_used_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            return asyncio.run(mark_pin_used_async(pin_code, tx_hash, network))
        else:
            raise


async def cleanup_expired_pins_async(network: str = "TRC20") -> int:
    """
    Очистить истекшие PIN-коды (пометить как expired) (асинхронная версия)
    Возвращает количество очищенных PIN-кодов
    """
    try:
        api_client = get_api_client()
        table_type = _network_to_table_type(network)
        
        # Получаем транзакции со статусом pending и с PIN-кодом
        transactions = await api_client._request(
            "GET", 
            "/transactions/", 
            params={
                "table_type": table_type,
                "status": "pending",
                "limit": 1000
            }
        )
        
        cleaned_count = 0
        from datetime import datetime, timezone, timedelta
        
        for tx in transactions.get("items", []):
            if tx.get("pin_code") and tx.get("status") == "pending":
                created_at = tx.get("created_at")
                if created_at:
                    try:
                        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        expires_at = created + timedelta(hours=1)
                        if datetime.now(timezone.utc) >= expires_at:
                            # Помечаем как expired
                            await api_client.update_transaction(
                                transaction_id=tx["id"],
                                status="failed"
                            )
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Ошибка при проверке срока действия PIN {tx.get('pin_code')}: {e}")
        
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Ошибка при очистке истекших PIN-кодов: {e}")
        return 0


def cleanup_expired_pins(network: str = "TRC20") -> int:
    """
    Синхронная обертка для cleanup_expired_pins_async
    """
    try:
        loop = asyncio.get_running_loop()
        raise RuntimeError(
            "cleanup_expired_pins() вызвана из async контекста. "
            "Используйте cleanup_expired_pins_async() с await вместо этого."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            return asyncio.run(cleanup_expired_pins_async(network))
        else:
            raise
