import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, Optional, Tuple
from config import GOOGLE_CREDENTIALS
import logging

logger = logging.getLogger(__name__)

class CommissionCalculator:
    def __init__(self):
        self.commission_data = None
        # Не загружаем данные при создании экземпляра
    
    def _load_commission_data(self):
        """Загружает данные о комиссиях из Google таблицы"""
        if self.commission_data is not None:
            return  # Уже загружено
        
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
            client = gspread.authorize(creds)
            
            # Открываем таблицу и лист с комиссиями
            sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Комиссии')
            
            # Получаем все записи
            records = sheet.get_all_records()
            
            # Преобразуем в словарь для быстрого доступа
            self.commission_data = {}
            for record in records:
                operation_type = record.get('Тип операции', '').strip()
                if operation_type:
                    self.commission_data[operation_type] = {
                        'min_amount': float(record.get('Мин. сумма', 0)),
                        'max_amount': float(record.get('Макс. сумма', 999999)),
                        'commission_type': record.get('Тип комиссии', '').strip(),
                        'commission_value': float(record.get('Значение комиссии', 0)),
                        'manager_required': record.get('Требуется менеджер', '').strip().lower() == 'да'
                    }
            
            logger.info(f"Загружено {len(self.commission_data)} правил комиссий")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных комиссий: {e}")
            # Устанавливаем значения по умолчанию
            self._set_default_commission_data()
    
    def _set_default_commission_data(self):
        """Устанавливает значения комиссий по умолчанию"""
        self.commission_data = {
            'USDT_to_USD': {
                'min_amount': 5000,
                'max_amount': 999999,
                'commission_type': 'manager',
                'commission_value': 0,
                'manager_required': True
            },
            'USDT_to_USD_medium': {
                'min_amount': 1000,
                'max_amount': 4999,
                'commission_type': 'percentage',
                'commission_value': -0.2,
                'manager_required': False
            },
            'USDT_to_USD_small': {
                'min_amount': 100,
                'max_amount': 999,
                'commission_type': 'fixed',
                'commission_value': 10,
                'manager_required': False
            },
            'USD_to_USDT': {
                'min_amount': 5000,
                'max_amount': 999999,
                'commission_type': 'manager',
                'commission_value': 0,
                'manager_required': True
            },
            'USD_to_USDT_medium': {
                'min_amount': 1000,
                'max_amount': 4999,
                'commission_type': 'percentage',
                'commission_value': 1.0,
                'manager_required': False
            },
            'USD_to_USDT_small': {
                'min_amount': 100,
                'max_amount': 999,
                'commission_type': 'fixed',
                'commission_value': 30,
                'manager_required': False
            }
        }
    
    def calculate_commission(self, operation_type: str, amount: float, current_rate: float = None) -> Dict:
        """
        Рассчитывает комиссию для операции обмена
        
        Args:
            operation_type: Тип операции ('USDT_to_USD' или 'USD_to_USDT')
            amount: Сумма операции
            current_rate: Текущий курс обмена (для процентных комиссий)
        
        Returns:
            Dict с информацией о комиссии
        """
        if not self.commission_data:
            self._load_commission_data()
        
        # Определяем подходящее правило комиссии
        rule = self._find_commission_rule(operation_type, amount)
        
        if not rule:
            return {
                'success': False,
                'error': 'Не найдено подходящее правило комиссии'
            }
        
        commission_amount = 0
        final_amount = amount
        
        if rule['commission_type'] == 'percentage':
            # Если курс не указан, используем 1.0 как значение по умолчанию
            rate_to_use = current_rate if current_rate is not None else 1.0
            commission_amount = (amount * rule['commission_value']) / 100
            final_amount = amount + commission_amount
        elif rule['commission_type'] == 'fixed':
            commission_amount = rule['commission_value']
            # Для USDT_to_USD комиссия вычитается (клиент получает меньше)
            # Для USD_to_USDT комиссия добавляется (клиент платит больше)
            if operation_type == 'USDT_to_USD':
                final_amount = amount - commission_amount
            else:
                final_amount = amount + commission_amount
        elif rule['commission_type'] == 'manager':
            commission_amount = 0
            final_amount = amount
        
        return {
            'success': True,
            'operation_type': operation_type,
            'original_amount': amount,
            'commission_amount': commission_amount,
            'final_amount': final_amount,
            'commission_type': rule['commission_type'],
            'commission_value': rule['commission_value'],
            'manager_required': rule['manager_required'],
            'rate_used': current_rate
        }
    
    def _find_commission_rule(self, operation_type: str, amount: float) -> Optional[Dict]:
        """Находит подходящее правило комиссии для суммы"""
        applicable_rules = []
        
        for rule_name, rule_data in self.commission_data.items():
            if rule_name.startswith(operation_type):
                if rule_data['min_amount'] <= amount <= rule_data['max_amount']:
                    applicable_rules.append((rule_name, rule_data))
        
        if not applicable_rules:
            # Если не найдено правило, используем логику по умолчанию
            if operation_type == 'USDT_to_USD':
                if amount >= 5000:
                    return {'commission_type': 'manager', 'commission_value': 0, 'manager_required': True}
                elif amount >= 1000:
                    return {'commission_type': 'percentage', 'commission_value': -0.2, 'manager_required': False}
                elif amount >= 100:
                    return {'commission_type': 'fixed', 'commission_value': 10, 'manager_required': False}
                else:
                    return {'commission_type': 'fixed', 'commission_value': 10, 'manager_required': False}
            elif operation_type == 'USD_to_USDT':
                if amount >= 5000:
                    return {'commission_type': 'manager', 'commission_value': 0, 'manager_required': True}
                elif amount >= 1000:
                    return {'commission_type': 'percentage', 'commission_value': 1.0, 'manager_required': False}
                elif amount >= 100:
                    return {'commission_type': 'fixed', 'commission_value': 30, 'manager_required': False}
                else:
                    return {'commission_type': 'fixed', 'commission_value': 30, 'manager_required': False}
            return None
        
        # Возвращаем первое подходящее правило
        return applicable_rules[0][1]
    
    def get_exchange_rate(self) -> Optional[float]:
        """Получает текущий курс обмена из Google таблицы"""
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
            client = gspread.authorize(creds)
            
            # Открываем лист с курсами
            sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Курсы')
            
            # Получаем курс USDT/USD
            rate_cell = sheet.find('USDT/USD')
            if rate_cell:
                rate_value = sheet.cell(rate_cell.row, rate_cell.col + 1).value
                return float(rate_value) if rate_value else None
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении курса обмена: {e}")
            # Возвращаем значение по умолчанию для USDT/USD
            return 1.0

# Создаем глобальный экземпляр калькулятора
commission_calculator = CommissionCalculator() 