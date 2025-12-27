"""
API клиент для взаимодействия бота с backend
"""
import aiohttp
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# URL backend API (из переменных окружения или по умолчанию)
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
BOT_API_KEY = os.getenv('BOT_API_KEY', '')  # API ключ для аутентификации бота


class BackendAPIError(Exception):
    """Исключение для ошибок API"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class BackendAPIClient:
    """Клиент для взаимодействия с backend API"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or BACKEND_API_URL).rstrip('/')
        self.api_key = api_key or BOT_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=10)  # 10 секунд таймаут
        
    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для запросов"""
        headers = {
            'Content-Type': 'application/json',
        }
        if self.api_key:
            headers['X-Bot-API-Key'] = self.api_key
        return headers
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Выполнить HTTP запрос"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers
                ) as response:
                    response_data = await response.json() if response.content_type == 'application/json' else {}
                    
                    if response.status >= 400:
                        error_msg = response_data.get('detail', response_data.get('message', f'HTTP {response.status}'))
                        logger.error(f"API Error {response.status}: {error_msg}")
                        raise BackendAPIError(error_msg, response.status)
                    
                    return response_data
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise BackendAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise BackendAPIError(f"Unexpected error: {str(e)}")
    
    # ========== ТРАНЗАКЦИИ ==========
    
    async def create_transaction(
        self,
        amount: float,
        currency: str,
        transaction_type: str,  # "buy" or "sell"
        table_type: str,  # "ERC", "TRC", "BEP"
        bot_id: Optional[int] = None,
        user_id: Optional[int] = None,
        hash: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        fee: Optional[float] = None,
        pin_code: Optional[str] = None,
        status: str = "pending"
    ) -> Dict[str, Any]:
        """Создать новую транзакцию"""
        data = {
            "amount": amount,
            "currency": currency,
            "transaction_type": transaction_type,
            "table_type": table_type,
            "status": status,
            "bot_id": bot_id,
            "user_id": user_id,
            "hash": hash,
            "from_address": from_address,
            "to_address": to_address,
            "fee": fee,
            "pin_code": pin_code
        }
        return await self._request("POST", "/transactions/", data=data)
    
    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Получить транзакцию по хешу"""
        try:
            transactions = await self._request("GET", "/transactions/", params={"hash": tx_hash})
            if transactions.get("items") and len(transactions["items"]) > 0:
                return transactions["items"][0]
            return None
        except BackendAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_transaction_by_pin(self, pin_code: str) -> Optional[Dict[str, Any]]:
        """Получить транзакцию по PIN-коду"""
        try:
            transactions = await self._request("GET", "/transactions/", params={"pin_code": pin_code})
            if transactions.get("items") and len(transactions["items"]) > 0:
                return transactions["items"][0]
            return None
        except BackendAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def update_transaction(
        self,
        transaction_id: int,
        status: Optional[str] = None,
        hash: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        fee: Optional[float] = None,
        confirmed_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Обновить транзакцию"""
        data = {}
        if status is not None:
            data["status"] = status
        if hash is not None:
            data["hash"] = hash
        if from_address is not None:
            data["from_address"] = from_address
        if to_address is not None:
            data["to_address"] = to_address
        if fee is not None:
            data["fee"] = fee
        if confirmed_at is not None:
            data["confirmed_at"] = confirmed_at.isoformat()
        
        return await self._request("PUT", f"/transactions/{transaction_id}", data=data)
    
    async def is_duplicate_transaction(self, tx_hash: str) -> bool:
        """Проверить, существует ли транзакция с таким хешем"""
        transaction = await self.get_transaction_by_hash(tx_hash)
        return transaction is not None
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    async def health_check(self) -> bool:
        """Проверить доступность API"""
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "healthy"
        except Exception:
            return False
    
    # ========== БОТЫ ==========
    
    async def get_bot_by_token(self, bot_token: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о боте по токену"""
        try:
            return await self._request("GET", f"/bots/by-token/{bot_token}")
        except BackendAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    # ========== КОМИССИИ ==========
    
    async def calculate_commission(
        self,
        bot_token: str,
        direction: str,  # "USDT_to_USD" or "USD_to_USDT"
        amount: float
    ) -> Dict[str, Any]:
        """
        Рассчитать комиссию через backend API
        
        Args:
            bot_token: Токен бота
            direction: Направление обмена (USDT_to_USD или USD_to_USDT)
            amount: Сумма для расчета
            
        Returns:
            Dict с полями:
            - amount_in: исходная сумма
            - commission: размер комиссии
            - amount_out: итоговая сумма (после комиссии)
            - rule_found: найдено ли правило
            - commission_type: тип комиссии (fixed/percentage)
            - commission_value: значение комиссии
        """
        data = {
            "bot_token": bot_token,
            "direction": direction,
            "amount": amount
        }
        return await self._request("POST", "/commission-rules/calculate-bot", data=data)


# Глобальный экземпляр клиента
_api_client: Optional[BackendAPIClient] = None


def get_api_client() -> BackendAPIClient:
    """Получить глобальный экземпляр API клиента"""
    global _api_client
    if _api_client is None:
        _api_client = BackendAPIClient()
    return _api_client

