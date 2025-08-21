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
TRC20_CONFIRMATIONS = 1
ERC20_CONFIRMATIONS = 6

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
    from tasks import check_erc20_confirmation_task
    """
    Проверяет транзакцию в зависимости от сети
    """
    if network == "TRC20":
        return await check_tron_transaction(tx_hash, target_address)
    elif network == "ERC20":
        check_erc20_confirmation_task.delay(tx_hash, target_address, username, chat_id, bot_id, lang)
    else:
        return {
            "success": False,
            "error": f"Неподдерживаемая сеть: {network}"
        }


def save_transaction_hash(google_params) -> bool:
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист4')


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

        # Открываем нужный лист
        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист4')

        # Ищем ячейку с transaction_hash
        cell = sheet.find(transaction_hash)

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
            data.get('operation', ''),  # Операция (Купить/Продать USD)
            data.get('amount', ''),  # Сумма USD
            data.get('city', ''),  # Город
            data.get('branch', ''),  # Отделение
            data.get('time', ''),  # Время визита
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