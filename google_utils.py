import gspread
from oauth2client.service_account import ServiceAccountCredentials
import aiohttp
import traceback
import csv
import json
from typing import Optional, Dict, Any
from config import ETHERSCAN_API_KEY, BSCSCAN_API_KEY, TRONSCAN_API_KEY

from config import logger, GOOGLE_CREDENTIALS 
import datetime

from utils.decode_etc20 import decode_erc20_input

from networks.tron import check_tron_transaction

def connect_to_sheet():
    print(f"✅ Заявка добавлена: {GOOGLE_CREDENTIALS}")
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Название_таблицы").sheet1  # Название как в Google Sheets
    return sheet

def save_data_to_sheet(data: dict):
    try:
        sheet = connect_to_sheet()
        sheet.append_row([
            data.get('crypto', ''),
            data.get('network', ''),
            data.get('amount', ''),
            data.get('contact', '')
        ])
        return True
    except Exception as e:
        print(f"Ошибка при сохранении в Google Таблицу: {e}")
        return False

# URL для получения данных кошельков
WALLET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo/export?format=csv&gid=2135417046"

# API endpoints для проверки транзакций
TRONSCAN_API = "https://api.tronscan.org/api"
ETHERSCAN_API = "https://api.etherscan.io/api"

# Настройки количества подтверждений
from config import TRC20_CONFIRMATIONS, ERC20_CONFIRMATIONS

def get_wallet_address(network: str) -> str:
    """
    Получает адрес кошелька для указанной сети из Google Sheets (Лист3)
    """
    try:
        # Подключаемся к Google Sheets
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Открываем таблицу и лист "Лист3"
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист3')

        # Получаем все строки таблицы
        records = sheet.get_all_records()

        for row in records:
            # row['Сеть'] должно совпадать с названием сети
            if row.get(' Сеть', '').strip().upper() == network.strip().upper():
                return row.get('Адрес кошелька')

        return None  # Если не нашли сеть
    except Exception as e:
        print(f"Ошибка при получении адреса кошелька: {e}")
        traceback.print_exc()
        return None

async def verify_transaction(tx_hash: str, network: str, target_address: str, username: int, chat_id: int, bot_id: int, lang) -> Dict[str, Any]:
    from tasks import check_confirmation_task
    """
    Проверяет транзакцию в зависимости от сети через асинхронную задачу
    """
    # Запускаем универсальную задачу проверки транзакции
    check_confirmation_task.delay(tx_hash, target_address, username, chat_id, bot_id, lang, network)
    
    # Возвращаем статус "обрабатывается" для всех сетей
    return {
        "success": True,
        "status": "processing",
        "message": "Транзакция проверяется..."
    }


def save_transaction_hash(google_params) -> bool:
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')


        sheet.append_row(google_params, value_input_option='USER_ENTERED')
        print(f"✅ Запись добавлена: {google_params}")
        return True

    except Exception as e:
        print(f"❌ Ошибка при сохранении хеша транзакции: {e}")
        return False

def save_crypto_request_to_sheet(data: dict) -> bool:
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу и выбираем "Лист5"
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист5')
        
        row = [
            data.get('currency', ''),
            data.get('amount', ''),
            data.get('network', ''),
            data.get('wallet_address', ''),
            data.get('visit_time', ''),
            data.get('client_name', ''),
            data.get('phone', ''),
            data.get('telegram', '')
        ]
        
        sheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"✅ Заявка добавлена: {row}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении в Google Sheets: {e}")
        return False

def update_transaction_status(transaction_hash: str, google_update_params) -> bool:
    try:
        # Авторизация
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Открываем нужный лист (TRC транзакции)
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')

        # Ищем ячейку с transaction_hash или первую пустую ячейку в колонке F
        if transaction_hash and transaction_hash.strip():
            cell = sheet.find(transaction_hash)
        else:
            # Если transaction_hash пустой, ищем первую строку с пустым хешем в колонке F
            records = sheet.get_all_records()
            cell = None
            for i, record in enumerate(records, start=2):  # начинаем с 2-й строки (после заголовков)
                tx_hash = record.get('Хеш транзакции', '')
                tx_hash_str = str(tx_hash).strip() if tx_hash is not None else ''
                if not tx_hash_str:  # Если ячейка пустая
                    # Создаем объект cell для пустой ячейки
                    class MockCell:
                        def __init__(self, row, col):
                            self.row = row
                            self.col = col
                    cell = MockCell(i, 6)  # Колонка F (6)
                    break

        if cell:
            # Допустим, колонка статуса — это 5-я колонка (как в твоей функции)
            for k, z in google_update_params.items():
                value_to_write, col_number = z[0], z[1]
                status_cell = sheet.cell(cell.row, col_number)
                
                logger.info(f"[google_utils] Проверка колонки {col_number} (текущее='{status_cell.value}', новое='{value_to_write}')")

                if status_cell.value != value_to_write:
                    sheet.update_cell(cell.row, col_number, value_to_write)
                    print(f"✅ Колонка {col_number} обновлена на '{value_to_write}' для транзакции {transaction_hash}")
                    # return True
                else:
                    print(f"⚠️ Колонка {col_number} уже установлена как '{value_to_write}'")
                    # return False
        else:
            print(f"❌ Транзакция {transaction_hash} не найдена")
            return False

    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса: {e}")
        return False


def save_cash_exchange_request_to_sheet(data: dict) -> bool:
    """
    Сохраняет заявку на обмен наличных в соответствующий лист Google таблицы
    
    Args:
        data: словарь с данными заявки, должен содержать 'operation' для определения листа
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Определяем лист в зависимости от операции
        operation = (data.get('operation', '') or '').strip()
        # Поддерживаем все локали: RU/UA/EN
        buy_variants = {'Купить USD', 'Купити USD', 'Buy USD'}
        sell_variants = {'Продать USD', 'Продати USD', 'Sell USD'}

        if any(v in operation for v in buy_variants):
            # Клиент покупает USD за UAH → лист "Заявка на обмен UAH → USD"
            sheet_name = 'Заявка на обмен UAH → USD'
        elif any(v in operation for v in sell_variants):
            # Клиент продает USD за UAH → лист "Заявка на обмен USD → UAH"
            sheet_name = 'Заявка на обмен USD → UAH'
        else:
            print(f"❌ Неизвестная операция: {operation}")
            return False
        
        # Открываем соответствующий лист
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Формируем строку для записи
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Дата и время
            data.get('request_number', ''),  # Номер заявки
            data.get('operation', ''),  # Операция (Купить/Продать USD)
            data.get('amount', ''),  # Сумма USD
            data.get('city', ''),  # Город
            data.get('branch', ''),  # Отделение
            data.get('name', ''),  # Имя клиента
            data.get('phone', ''),  # Телефон
            data.get('telegram', ''),  # Telegram username
            'Новая'  # Статус заявки
        ]
        
        sheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"✅ Заявка на обмен наличных добавлена в лист '{sheet_name}': {row}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении заявки на обмен наличных: {e}")
        return False

def save_transaction_tracking_to_sheet(transaction_data: dict):
    """Сохраняет данные отслеживания транзакции в Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу для отслеживания транзакций
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций')
        
        # Добавляем строку с данными
        row_data = [
            transaction_data.get('amount', ''),
            transaction_data.get('initiator_user_id', ''),
            transaction_data.get('tx_hash_user_id', ''),
            transaction_data.get('network', ''),
            transaction_data.get('operation', ''),
            transaction_data.get('tx_hash', ''),
            transaction_data.get('started_at', ''),
            transaction_data.get('status', ''),
            datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        ]
        
        sheet.append_row(row_data)
        print(f"✅ Данные отслеживания сохранены в Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении данных отслеживания: {e}")
        return False

def save_trc_transaction_tracking_to_sheet(transaction_data: dict):
    """Сохраняет данные отслеживания TRC транзакции в Google Sheets с PIN-кодом и номером телефона"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу для отслеживания TRC транзакций
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')
        
        # Добавляем строку с данными согласно структуре таблицы из скриншота:
        # A: Сумма USDT, B: ID инициатора, C: ID введшего хеш, D: Сеть, E: Операция, 
        # F: Хеш транзакции, G: Время начала, H: Статус, I: Время записи, 
        # J: ID пользователя, K: PIN-code, L: Номер телефон
        
        row_data = [
            transaction_data.get('amount', ''),                    # A: Сумма USDT
            transaction_data.get('initiator_user_id', ''),         # B: ID инициатора
            transaction_data.get('tx_hash_user_id', ''),           # C: ID введшего хеш
            transaction_data.get('network', ''),                   # D: Сеть
            transaction_data.get('operation', ''),                 # E: Операция
            transaction_data.get('tx_hash', ''),                  # F: Хеш транзакции
            transaction_data.get('started_at', ''),                # G: Время начала
            transaction_data.get('status', ''),                    # H: Статус
            datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S'), # I: Время записи
            transaction_data.get('pin_user_id', transaction_data.get('initiator_user_id', '')), # J: ID пользователя
            transaction_data.get('pin_code', ''),                  # K: PIN-code
            transaction_data.get('phone_number', '')                # L: Номер телефон
        ]
        
        # Вставляем строку в позицию 2 (сразу после заголовков)
        # Это обеспечит добавление новых транзакций в верх таблицы
        sheet.insert_row(row_data, 2)
        
        print(f"✅ Данные TRC транзакции сохранены в Google Sheets с PIN-кодом и номером телефона")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении данных TRC транзакции: {e}")
        return False

def update_trc_transaction_status(tx_hash: str, status: str) -> bool:
    """Обновляет статус транзакции в листе TRC"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем лист TRC
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')
        
        # Ищем ячейку с transaction_hash (колонка F - 6-я колонка)
        cell = sheet.find(tx_hash)
        
        if cell:
            # Обновляем статус в колонке H (8-я колонка)
            sheet.update_cell(cell.row, 8, status)
            print(f"✅ Статус транзакции {tx_hash} обновлен на {status} в строке {cell.row}")
            return True
        else:
            print(f"❌ Транзакция {tx_hash} не найдена в листе TRC")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса TRC транзакции: {e}")
        return False

def update_trc_transaction_hash(old_tx_hash: str, new_tx_hash: str) -> bool:
    """Обновляет хеш транзакции в листе TRC"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем лист TRC
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')
        
        # Получаем все записи для поиска
        records = sheet.get_all_records()
        
        # Ищем строку с пустым хешем транзакции (первая строка с пустым хешем)
        for i, record in enumerate(records, start=2):  # начинаем с 2-й строки (после заголовков)
            tx_hash = record.get('Хеш транзакции', '')
            # Безопасно преобразуем в строку и убираем пробелы
            tx_hash_str = str(tx_hash).strip() if tx_hash is not None else ''
            if not tx_hash_str or tx_hash_str == old_tx_hash:  # Если ячейка пустая или содержит старый хеш
                sheet.update_cell(i, 6, new_tx_hash)  # Обновляем хеш транзакции в колонке F
                print(f"✅ Хеш транзакции обновлен на {new_tx_hash} в строке {i}")
                return True
        
        print(f"❌ Не удалось найти подходящую ячейку для хеша транзакции")
        return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении хеша TRC транзакции: {e}")
        return False

def update_trc_transaction_phone(user_id: int, phone_number: str) -> bool:
    """Обновляет номер телефона в листе TRC для конкретного пользователя"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Открываем лист TRC
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')
        
        # Получаем все записи для поиска
        records = sheet.get_all_records()
        
        # Ищем строку с данным user_id в колонке B (ID инициатора)
        for i, record in enumerate(records, start=2):  # начинаем с 2-й строки (после заголовков)
            # Проверяем разные варианты ID инициатора
            initiator_id = record.get('ID инициатора', '')
            # Безопасно преобразуем в строку и убираем пробелы
            initiator_id_str = str(initiator_id).strip() if initiator_id is not None else ''
            if str(user_id) == initiator_id_str:
                # Обновляем номер телефона в колонке L (12-я колонка)
                sheet.update_cell(i, 12, phone_number)
                print(f"✅ Номер телефона {phone_number} обновлен для пользователя {user_id} в строке {i}")
                return True
        
        print(f"❌ Пользователь {user_id} не найден в листе TRC. Доступные ID: {[r.get('ID инициатора', '') for r in records[:3]]}")
        return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении номера телефона TRC транзакции: {e}")
        return False