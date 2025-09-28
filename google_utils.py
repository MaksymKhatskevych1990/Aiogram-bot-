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
from config import TRONSCAN_API
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
    Проверяет транзакцию в зависимости от сети
    """
    check_confirmation_task.delay(tx_hash, target_address, username, chat_id, bot_id, lang, network)
    # if network == "TRC20" or network == "ERC20":
    #     check_confirmation_task.delay(tx_hash, target_address, username, chat_id, bot_id, lang, network)
    # else:
    #     return {
    #         "success": False,
    #         "error": f"Неподдерживаемая сеть: {network}"
    #     }


def is_duplicate_transaction(tx_hash: str) -> bool:
    """
    Проверяет дубликаты транзакций в обеих таблицах (TRC и ERC)
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Проверяем в таблице TRC транзакций
        trc_sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')
        trc_cell = trc_sheet.find(tx_hash)
        
        # Проверяем в таблице ERC транзакций
        erc_sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакции ERC')
        erc_cell = erc_sheet.find(tx_hash)
        
        return trc_cell is not None or erc_cell is not None

    except Exception as e:
        print(f"❌ Ошибка при проверке дубликата: {e}")
        return False

def is_transaction_exists_in_trc_sheet(tx_hash: str) -> bool:
    """
    Проверяет, существует ли транзакция в таблице "Отслеживание транзакций TRC"
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Отслеживание транзакций TRC')

        # Ищем хеш в колонке J (индекс 10)
        cell = sheet.find(tx_hash)
        return cell is not None

    except Exception as e:
        print(f"❌ Ошибка при проверке существования транзакции в TRC таблице: {e}")
        return False

def save_transaction_hash(google_params, network="TRC20") -> bool:
    try:
        tx_hash = google_params[1]  # Получаем хеш транзакции
        
        # Проверяем, не существует ли уже такая транзакция
        if is_duplicate_transaction(tx_hash):
            print(f"⚠️ Транзакция {tx_hash} уже существует в таблице, пропускаем запись")
            return True  # Возвращаем True, так как запись уже есть
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)

        # google_params содержит: [username, tx_hash, target_address, timestamp, now, status, amount, error, phone]
        
        if network == "ERC20":
            # Структура ERC таблицы ИДЕНТИЧНА TRC: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
            # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
            # K: Id пользователя, L: Номер телефона, M: Chat ID
            row_data = [
                google_params[6],  # A: Сумма USDT (amount)
                '',                # B: Кошелек пользователя (пока пустой)
                '',                # C: PIN-code (пока пустой)
                google_params[2],  # D: Адрес для перевода (target_address)
                network,           # E: Сеть (ERC20)
                google_params[6],  # F: Сумма (дублируем amount)
                google_params[4],  # G: Время создания (now)
                '',                # H: Время истечения (пока пустое)
                google_params[5],  # I: Статус (status)
                google_params[1],  # J: tx_hash ← ВОТ ГДЕ ДОЛЖЕН БЫТЬ ХЕШ!
                google_params[0],  # K: Id пользователя (username)
                google_params[8] if len(google_params) > 8 else '',  # L: Номер телефона
                ''                 # M: Chat ID (пока пустой)
            ]
        else:
            # Структура TRC таблицы: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
            # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
            # K: Id пользователя, L: Номер телефона, M: Chat ID
            row_data = [
                google_params[6],  # A: Сумма USDT (amount)
                '',                # B: Кошелек пользователя (пока пустой)
                '',                # C: PIN-code (пока пустой)
                google_params[2],  # D: Адрес для перевода (target_address)
                '',                # E: Сеть (пока пустая)
                google_params[6],  # F: Сумма (дублируем amount)
                google_params[4],  # G: Время создания (now)
                '',                # H: Время истечения (пока пустое)
                google_params[5],  # I: Статус (status)
                google_params[1],  # J: tx_hash
                google_params[0],  # K: Id пользователя (username)
                google_params[8] if len(google_params) > 8 else '',  # L: Номер телефона
                ''                 # M: Chat ID (пока пустой)
            ]

        sheet.append_row(row_data, value_input_option='USER_ENTERED')
        print(f"✅ Запись добавлена в правильном формате: {row_data}")
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

def update_transaction_status(transaction_hash: str, google_update_params, network="TRC20") -> bool:
    try:
        # Авторизация
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)

        # Ищем ячейку с transaction_hash
        cell = sheet.find(transaction_hash)

        if cell:
            # Обновляем параметры в зависимости от сети
            for k, z in google_update_params.items():
                value_to_write, col_number = z[0], z[1]
                
                # Для ERC20 структура ИДЕНТИЧНА TRC - никаких корректировок не нужно
                # if network == "ERC20":
                #     # ERC20 и TRC20 имеют одинаковую структуру колонок
                
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


# =============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С PIN-КОДАМИ
# =============================================================================

import random
import string
from datetime import datetime, timedelta

def generate_pin_code() -> str:
    """
    Генерирует уникальный 6-цифровой PIN-код, который не начинается с 0
    """
    # Первая цифра: 1-9 (не может быть 0)
    first_digit = random.choice('123456789')
    
    # Остальные 5 цифр: 0-9
    remaining_digits = ''.join(random.choices(string.digits, k=5))
    
    return first_digit + remaining_digits

def save_pin_code(user_wallet: str, target_wallet: str, network: str, amount: float, 
                  phone: str, user_id: int, chat_id: int = None, expires_hours: int = 1) -> str:
    """
    Сохраняет PIN-код в таблицу "Отслеживание транзакций TRC"
    
    Args:
        user_wallet: Кошелек пользователя
        target_wallet: Адрес бота для перевода
        network: Сеть (ERC20/TRC20)
        amount: Сумма USDT
        phone: Номер телефона
        user_id: ID пользователя Telegram
        expires_hours: Через сколько часов истекает PIN (по умолчанию 1 час)
    
    Returns:
        str: Сгенерированный PIN-код или None при ошибке
    """
    try:
        # Генерируем уникальный PIN-код
        pin_code = generate_pin_code()
        
        # Проверяем уникальность PIN-кода
        while is_pin_exists(pin_code, network):
            pin_code = generate_pin_code()
        
        # Подключаемся к Google Sheets
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Вычисляем время создания и истечения
        now = datetime.now()
        expires_at = now + timedelta(hours=expires_hours)
        
        # Формируем строку для записи в правильном порядке колонок
        if network == "ERC20":
            # Структура ERC таблицы ИДЕНТИЧНА TRC: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
            # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
            # K: Id пользователя, L: Номер телефона, M: Chat ID
            row = [
                amount,               # A: Сумма USDT
                user_wallet,          # B: Кошелек пользователя
                pin_code,             # C: PIN-код
                target_wallet,        # D: Адрес для перевода
                network,              # E: Сеть (ERC20)
                amount,               # F: Сумма (дублируем amount)
                now.strftime("%Y-%m-%d %H:%M:%S"),  # G: Время создания
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),  # H: Время истечения
                'active',             # I: Статус
                '',                   # J: tx_hash (пока пустой)
                user_id,              # K: Id пользователя
                phone,                # L: Номер телефона
                chat_id or ''         # M: Chat ID
            ]
        else:
            # Структура TRC таблицы: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
            # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
            # K: Id пользователя, L: Номер телефона, M: Chat ID
            row = [
                amount,               # A: Сумма USDT
                user_wallet,          # B: Кошелек пользователя
                pin_code,            # C: PIN-код
                target_wallet,        # D: Адрес для перевода
                network,             # E: Сеть
                amount,              # F: Сумма (дублируем для совместимости)
                now.strftime("%Y-%m-%d %H:%M:%S"),  # G: Время создания
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),  # H: Время истечения
                'active',            # I: Статус
                '',                  # J: tx_hash (пока пустой)
                user_id,             # K: Id пользователя (user_id)
                phone,               # L: Номер телефона
                chat_id or ''        # M: Chat ID для уведомлений (не дублируем user_id)
            ]
        
        # Добавляем строку в таблицу
        sheet.append_row(row, value_input_option='USER_ENTERED')
        
        print(f"✅ PIN-код {pin_code} сохранен для пользователя {user_id}")
        return pin_code
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении PIN-кода: {e}")
        return None

def is_pin_exists(pin_code: str, network: str = "TRC20") -> bool:
    """
    Проверяет, существует ли PIN-код в таблице
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Получаем все PIN-коды из колонки C (третья колонка, индекс 3)
        all_pins = sheet.col_values(3)
        return pin_code in all_pins
        
    except Exception as e:
        print(f"❌ Ошибка при проверке существования PIN-кода: {e}")
        return False

def validate_pin_code(pin_code: str, network: str = "TRC20") -> dict:
    """
    Проверяет PIN-код и его срок действия
    
    Returns:
        dict: {
            'valid': bool,
            'data': dict or None,
            'error': str or None
        }
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Получаем все записи
        records = sheet.get_all_records()
        
        for record in records:
            if record.get('pin_code') == pin_code:
                # Проверяем статус
                if record.get('status') == 'used':
                    return {
                        'valid': False,
                        'data': None,
                        'error': 'PIN-код уже использован'
                    }
                
                if record.get('status') == 'expired':
                    return {
                        'valid': False,
                        'data': None,
                        'error': 'PIN-код истек'
                    }
                
                # Проверяем срок действия
                expires_str = record.get('expires_at')
                if expires_str:
                    try:
                        expires_at = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
                        if datetime.now() > expires_at:
                            # Помечаем как истекший
                            mark_pin_expired(pin_code)
                            return {
                                'valid': False,
                                'data': None,
                                'error': 'PIN-код истек'
                            }
                    except ValueError:
                        pass
                
                return {
                    'valid': True,
                    'data': record,
                    'error': None
                }
        
        return {
            'valid': False,
            'data': None,
            'error': 'PIN-код не найден'
        }
        
    except Exception as e:
        print(f"❌ Ошибка при валидации PIN-кода: {e}")
        return {
            'valid': False,
            'data': None,
            'error': f'Ошибка валидации: {str(e)}'
        }

def mark_pin_used(pin_code: str, tx_hash: str, network: str = "TRC20") -> bool:
    """
    Помечает PIN-код как использованный и добавляет хеш транзакции
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Ищем ячейку с PIN-кодом
        if network == "ERC20":
            # В ERC таблице PIN-код находится в колонке C (индекс 3) - как в TRC
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем статус на 'used' (колонка I, индекс 9) - как в TRC
                sheet.update_cell(cell.row, 9, 'used')
                # Обновляем хеш транзакции (колонка J, индекс 10) - как в TRC
                sheet.update_cell(cell.row, 10, tx_hash)
                
                print(f"✅ PIN-код {pin_code} помечен как использованный, хеш {tx_hash} записан в колонку J")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
        else:
            # В TRC таблице PIN-код находится в колонке C (индекс 3)
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем статус на 'used' (колонка I, индекс 9)
                sheet.update_cell(cell.row, 9, 'used')
                # Обновляем хеш транзакции (колонка J, индекс 10)
                sheet.update_cell(cell.row, 10, tx_hash)
                
                print(f"✅ PIN-код {pin_code} помечен как использованный, хеш {tx_hash} записан в колонку J")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении PIN-кода: {e}")
        return False

def mark_pin_expired(pin_code: str, network: str = "TRC20") -> bool:
    """
    Помечает PIN-код как истекший
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Ищем ячейку с PIN-кодом
        if network == "ERC20":
            # В ERC таблице PIN-код находится в колонке C (индекс 3) - как в TRC
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем статус на 'expired' (колонка I, индекс 9) - как в TRC
                sheet.update_cell(cell.row, 9, 'expired')
                print(f"✅ PIN-код {pin_code} помечен как истекший")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
        else:
            # В TRC таблице PIN-код находится в колонке C (индекс 3)
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем статус на 'expired' (колонка I, индекс 9)
                sheet.update_cell(cell.row, 9, 'expired')
                print(f"✅ PIN-код {pin_code} помечен как истекший")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении PIN-кода: {e}")
        return False

def get_active_pins(network: str = "TRC20") -> list:
    """
    Получает все активные PIN-коды для мониторинга
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Получаем все записи (начиная со второй строки, так как первая - заголовки)
        all_values = sheet.get_all_values()
        if len(all_values) < 2:
            return []
        
        # Пропускаем заголовки (первая строка)
        data_rows = all_values[1:]
        active_pins = []
        
        for row in data_rows:
            if network == "ERC20":
                if len(row) < 13:  # ERC таблица имеет 13 колонок (как TRC)
                    continue
                    
                # Структура ERC таблицы ИДЕНТИЧНА TRC: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
                # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
                # K: Id пользователя, L: Номер телефона, M: Chat ID
                record = {
                    'amount': row[0],           # A: Сумма USDT
                    'user_wallet': row[1],      # B: Кошелек пользователя
                    'pin_code': row[2],         # C: PIN-код
                    'target_wallet': row[3],    # D: Адрес для перевода
                    'network': row[4],          # E: Сеть
                    'amount_duplicate': row[5], # F: Сумма (дублируем amount)
                    'created_at': row[6],       # G: Время создания
                    'expires_at': row[7],       # H: Время истечения
                    'status': row[8],           # I: Статус
                    'tx_hash': row[9],          # J: tx_hash
                    'user_id': row[10],         # K: Id пользователя
                    'phone': row[11],           # L: Номер телефона
                    'chat_id': row[12] if len(row) > 12 else ''  # M: Chat ID
                }
            else:
                if len(row) < 12:  # TRC таблица имеет 13 колонок
                    continue
                    
                # Структура TRC таблицы: A: Сумма USDT, B: Кошелек пользователя, C: PIN-code, D: Адрес для перевода, 
                # E: Сеть, F: Сумма, G: Время создания, H: Время истечения, I: Статус, J: tx_hash, 
                # K: Id пользователя, L: Номер телефона, M: Chat ID
                record = {
                    'amount': row[0],           # A: Сумма USDT
                    'user_wallet': row[1],      # B: Кошелек пользователя
                    'pin_code': row[2],         # C: PIN-код
                    'target_wallet': row[3],     # D: Адрес для перевода
                    'network': row[4],          # E: Сеть
                    'amount_duplicate': row[5],  # F: Сумма (дубликат)
                    'created_at': row[6],       # G: Время создания
                    'expires_at': row[7],       # H: Время истечения
                    'status': row[8],           # I: Статус
                    'tx_hash': row[9],          # J: tx_hash
                    'user_id': row[10],         # K: Id пользователя
                    'phone': row[11],           # L: Номер телефона
                    'chat_id': row[12] if len(row) > 12 else ''  # M: Chat ID (не дублируем user_id)
                }
            
            if record.get('status') == 'active':
                if network == "ERC20":
                    # В ERC таблице нет поля expires_at, просто добавляем активные PIN-коды
                    active_pins.append(record)
                else:
                    # В TRC таблице проверяем срок действия
                    expires_str = record.get('expires_at')
                    if expires_str:
                        try:
                            expires_at = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
                            if datetime.now() <= expires_at:
                                active_pins.append(record)
                            else:
                                # Помечаем как истекший
                                mark_pin_expired(record.get('pin_code'), network)
                        except ValueError:
                            pass
                    else:
                        active_pins.append(record)
        
        return active_pins
        
    except Exception as e:
        print(f"❌ Ошибка при получении активных PIN-кодов: {e}")
        return []

def update_pin_phone(pin_code: str, phone: str, network: str = "TRC20") -> bool:
    """
    Обновляет номер телефона для существующего PIN-кода
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Ищем ячейку с PIN-кодом
        if network == "ERC20":
            # В ERC таблице PIN-код находится в колонке C (индекс 3) - как в TRC
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем номер телефона (колонка L, индекс 12) - как в TRC
                sheet.update_cell(cell.row, 12, phone)
                
                print(f"✅ Номер телефона {phone} обновлен для PIN-кода {pin_code} в колонке L")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
        else:
            # В TRC таблице PIN-код находится в колонке C (индекс 3)
            cell = sheet.find(pin_code)
            if cell:
                # Обновляем номер телефона (колонка L, индекс 12)
                sheet.update_cell(cell.row, 12, phone)
                
                print(f"✅ Номер телефона {phone} обновлен для PIN-кода {pin_code} в колонке L")
                return True
            else:
                print(f"❌ PIN-код {pin_code} не найден")
                return False
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении номера телефона: {e}")
        return False

def get_phone_by_pin(pin_code: str, network: str = "TRC20") -> str:
    """
    Получает номер телефона по PIN-коду
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Ищем ячейку с PIN-кодом
        cell = sheet.find(pin_code)
        
        if cell:
            if network == "ERC20":
                # В ERC таблице номер телефона в колонке L (индекс 12)
                phone_cell = sheet.cell(cell.row, 12)
            else:
                # В TRC таблице номер телефона в колонке L (индекс 12)
                phone_cell = sheet.cell(cell.row, 12)
            
            return phone_cell.value or ""
        else:
            return ""
            
    except Exception as e:
        print(f"❌ Ошибка при получении номера телефона по PIN-коду: {e}")
        return ""

def cleanup_expired_pins(network: str = "TRC20") -> int:
    """
    Очищает истекшие PIN-коды (помечает их как expired)
    Возвращает количество очищенных PIN-кодов
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        
        # Выбираем правильный лист в зависимости от сети
        if network == "ERC20":
            sheet_name = 'Отслеживание транзакции ERC'
        else:
            sheet_name = 'Отслеживание транзакций TRC'
            
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet(sheet_name)
        
        # Получаем все записи
        records = sheet.get_all_records()
        cleaned_count = 0
        
        for i, record in enumerate(records, start=2):  # Начинаем с 2-й строки (пропускаем заголовок)
            if record.get('status') == 'active':
                if network == "ERC20":
                    # В ERC таблице нет поля expires_at, пропускаем очистку
                    pass
                else:
                    # В TRC таблице проверяем срок действия
                    expires_str = record.get('expires_at')
                    if expires_str:
                        try:
                            expires_at = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
                            if datetime.now() > expires_at:
                                # Помечаем как истекший
                                # ERC20 и TRC20 имеют одинаковую структуру - колонка I (индекс 9)
                                sheet.update_cell(i, 9, 'expired')  # Колонка I - статус
                                cleaned_count += 1
                        except ValueError:
                            pass
        
        if cleaned_count > 0:
            print(f"✅ Очищено {cleaned_count} истекших PIN-кодов")
        
        return cleaned_count
        
    except Exception as e:
        print(f"❌ Ошибка при очистке истекших PIN-кодов: {e}")
        return 0