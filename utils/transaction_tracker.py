import json
import redis
from datetime import datetime, timedelta
from typing import Dict, Optional
from config import REDIS_URL

class TransactionTracker:
    def __init__(self):
        self.redis_client = redis.from_url(REDIS_URL, db=4, decode_responses=True)
        self.session_ttl = 24 * 60 * 60  # 24 часа TTL для сессии
    
    def start_transaction_session(self, user_id: int, operation: str, network: str, amount: float) -> str:
        """Начинает сессию транзакции для пользователя"""
        session_id = f"tx_session_{user_id}_{datetime.now().timestamp()}"
        
        session_data = {
            'user_id': user_id,
            'operation': operation,
            'network': network,
            'amount': amount,
            'started_at': datetime.now().isoformat(),
            'status': 'started',
            'tx_hash': None,
            'tx_hash_user_id': None,
            'completed_at': None
        }
        
        # Сохраняем сессию
        self.redis_client.setex(
            f"session:{session_id}", 
            self.session_ttl, 
            json.dumps(session_data)
        )
        
        # Также сохраняем активную сессию для пользователя
        self.redis_client.setex(
            f"active_session:{user_id}", 
            self.session_ttl, 
            session_id
        )
        
        print(f"🟢 НАЧАТА ТРАНЗАКЦИЯ:")
        print(f"   📊 Сессия: {session_id}")
        print(f"   �� Пользователь ID: {user_id}")
        print(f"   💰 Операция: {operation}")
        print(f"   �� Сеть: {network}")
        print(f"   �� Сумма: {amount} USDT")
        print(f"   ⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print("-" * 50)
        
        return session_id
    
    def get_active_session(self, user_id: int) -> Optional[Dict]:
        """Получает активную сессию пользователя"""
        session_id = self.redis_client.get(f"active_session:{user_id}")
        if not session_id:
            return None
        
        session_data = self.redis_client.get(f"session:{session_id}")
        if session_data:
            return json.loads(session_data)
        return None
    
    def add_transaction_hash(self, user_id: int, tx_hash: str) -> Dict:
        """Добавляет хеш транзакции и проверяет пользователя"""
        session_data = self.get_active_session(user_id)
        
        if not session_data:
            return {
                'success': False,
                'error': 'NO_ACTIVE_SESSION',
                'message': 'Нет активной сессии транзакции'
            }
        
        # Проверяем, что пользователь тот же
        if session_data['user_id'] != user_id:
            print(f"�� ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ:")
            print(f"   ⚠️  Пользователь {user_id} пытается ввести хеш для сессии пользователя {session_data['user_id']}")
            print(f"   🔗 Хеш транзакции: {tx_hash}")
            print(f"   📊 Сессия: {session_data.get('session_id', 'unknown')}")
            print("-" * 50)
            
            return {
                'success': False,
                'error': 'USER_MISMATCH',
                'message': 'Пользователь не совпадает с инициатором транзакции'
            }
        
        # Обновляем сессию
        session_data['tx_hash'] = tx_hash
        session_data['tx_hash_user_id'] = user_id
        session_data['status'] = 'hash_added'
        session_data['hash_added_at'] = datetime.now().isoformat()
        
        # Сохраняем обновленную сессию
        session_id = self.redis_client.get(f"active_session:{user_id}")
        if session_id:
            self.redis_client.setex(
                f"session:{session_id}", 
                self.session_ttl, 
                json.dumps(session_data)
            )
        
        print(f"✅ ХЕШ ТРАНЗАКЦИИ ДОБАВЛЕН:")
        print(f"   📊 Сессия: {session_id}")
        print(f"   �� Пользователь ID: {user_id}")
        print(f"   🔗 Хеш: {tx_hash}")
        print(f"   💰 Сумма: {session_data['amount']} USDT")
        print(f"   🌐 Сеть: {session_data['network']}")
        print(f"   ⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print("-" * 50)
        
        return {
            'success': True,
            'session_data': session_data,
            'message': 'Хеш транзакции успешно добавлен'
        }
    
    def complete_transaction(self, user_id: int, success: bool = True) -> Dict:
        """Завершает транзакцию"""
        session_data = self.get_active_session(user_id)
        
        if not session_data:
            return {
                'success': False,
                'error': 'NO_ACTIVE_SESSION',
                'message': 'Нет активной сессии транзакции'
            }
        
        # Обновляем статус
        session_data['status'] = 'completed' if success else 'failed'
        session_data['completed_at'] = datetime.now().isoformat()
        
        # Сохраняем обновленную сессию
        session_id = self.redis_client.get(f"active_session:{user_id}")
        if session_id:
            self.redis_client.setex(
                f"session:{session_id}", 
                self.session_ttl, 
                json.dumps(session_data)
            )
        
        # Удаляем активную сессию
        self.redis_client.delete(f"active_session:{user_id}")
        
        status_emoji = "✅" if success else "❌"
        status_text = "ЗАВЕРШЕНА" if success else "ОТКЛОНЕНА"
        
        print(f"{status_emoji} ТРАНЗАКЦИЯ {status_text}:")
        print(f"   📊 Сессия: {session_id}")
        print(f"   �� Пользователь ID: {user_id}")
        print(f"   💰 Сумма: {session_data['amount']} USDT")
        print(f"   🌐 Сеть: {session_data['network']}")
        print(f"   �� Хеш: {session_data.get('tx_hash', 'N/A')}")
        print(f"   ⏰ Время завершения: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print("-" * 50)
        
        return {
            'success': True,
            'session_data': session_data,
            'message': f'Транзакция {"завершена" if success else "отклонена"}'
        }
    
    def get_transaction_summary(self, user_id: int) -> Dict:
        """Получает сводку по транзакции для логирования"""
        session_data = self.get_active_session(user_id)
        
        if not session_data:
            return {
                'success': False,
                'error': 'NO_ACTIVE_SESSION'
            }
        
        return {
            'success': True,
            'summary': {
                'amount': session_data['amount'],
                'initiator_user_id': session_data['user_id'],
                'tx_hash_user_id': session_data.get('tx_hash_user_id'),
                'network': session_data['network'],
                'operation': session_data['operation'],
                'tx_hash': session_data.get('tx_hash'),
                'started_at': session_data['started_at'],
                'status': session_data['status']
            }
        }

# Глобальный экземпляр
transaction_tracker = TransactionTracker()