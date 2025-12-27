"""
Утилиты для работы с блокчейном и backend API
Все функции для работы с Google Sheets удалены - теперь работаем только с БД
"""

from typing import Optional, Dict, Any
from config import logger
from utils.api_client import get_api_client
from config import get_current_bot_token


async def get_wallet_address_from_backend(network: str, bot_token: str = None) -> Optional[str]:
    """
    Получает адрес кошелька для указанной сети из базы данных backend
    Это адрес кошелька бота, на который пользователи должны переводить средства
    """
    try:
        # Используем переданный токен или токен из конфига
        token = bot_token or get_current_bot_token()
        if not token:
            logger.warning("Bot token not available for getting wallet address from backend")
            return None
        
        api_client = get_api_client()
        bot_info = await api_client.get_bot_by_token(token)
        
        if not bot_info:
            logger.warning(f"Bot not found in backend for token (first 10 chars: {token[:10] if token else 'None'}...)")
            return None
        
        # Детальное логирование для отладки
        logger.info(f"=== ПОЛУЧЕНИЕ АДРЕСА КОШЕЛЬКА ИЗ БД ===")
        logger.info(f"Сеть: {network}")
        logger.info(f"Информация о боте: {bot_info.get('bot_name', 'Unknown')} (@{bot_info.get('bot_username', 'Unknown')})")
        logger.info(f"Адреса в БД: ERC={bot_info.get('wallet_address_erc')}, TRC={bot_info.get('wallet_address_trc')}, BEP={bot_info.get('wallet_address_bep')}")
        
        # Определяем поле адреса в зависимости от сети
        network_upper = network.strip().upper()
        wallet_address = None
        
        if "ERC" in network_upper or "ETH" in network_upper:
            wallet_address = bot_info.get("wallet_address_erc")
            logger.info(f"Выбран адрес ERC20: {wallet_address}")
        elif "BEP" in network_upper or "BSC" in network_upper:
            wallet_address = bot_info.get("wallet_address_bep")
            logger.info(f"Выбран адрес BEP20: {wallet_address}")
        else:
            # По умолчанию TRC20
            wallet_address = bot_info.get("wallet_address_trc")
            logger.info(f"Выбран адрес TRC20: {wallet_address}")
        
        if wallet_address:
            logger.info(f"✅ Получен адрес кошелька для сети {network}: {wallet_address} (из базы данных)")
        else:
            logger.warning(f"❌ Адрес кошелька для сети {network} не настроен в базе данных для бота {bot_info.get('bot_name', 'Unknown')}")
        
        return wallet_address
            
    except Exception as e:
        logger.error(f"Ошибка при получении адреса кошелька из backend: {e}", exc_info=True)
        return None


async def verify_transaction(tx_hash: str, network: str, target_address: str, username: int, chat_id: int, bot_id: int, lang) -> Dict[str, Any]:
    """
    Проверяет транзакцию в зависимости от сети
    Запускает задачу проверки транзакции в Celery
    """
    from tasks import check_confirmation_task
    check_confirmation_task.delay(tx_hash, target_address, username, chat_id, bot_id, lang, network)
    return {"success": True, "message": "Проверка транзакции запущена"}
