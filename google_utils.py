# google_utils.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import aiohttp
import traceback
import csv
import json
from typing import Optional, Dict, Any
from config import ETHERSCAN_API_KEY, BSCSCAN_API_KEY, TRONSCAN_API_KEY

from config import logger
import datetime

from utils.decode_etc20 import decode_erc20_input

from networks.tron import check_tron_transaction
from networks.ethereum import check_ethereum_transaction

def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
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
BSCSCAN_API = "https://api.bscscan.com/api"

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
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
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

async def check_bsc_transaction(tx_hash: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию в сети BSC через BSCScan API
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{BSCSCAN_API}"
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": BSCSCAN_API_KEY
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("result"):
                        tx_data = data["result"]
                        # Проверяем статус транзакции
                        if tx_data.get("to", "").lower() == target_address.lower():
                            return {
                                "success": True,
                                "status": "confirmed",
                                "amount": int(tx_data.get("value", "0"), 16),
                                "from": tx_data.get("from", ""),
                                "to": tx_data.get("to", ""),
                                "blockNumber": tx_data.get("blockNumber")
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Транзакция направлена на другой адрес"
                            }
                    else:
                        return {
                            "success": False,
                            "error": "Транзакция не найдена"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Ошибка API: {response.status}"
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка проверки транзакции: {str(e)}"
        }

async def verify_transaction(tx_hash: str, network: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию в зависимости от сети
    """
    if network == "TRC20":
        return await check_tron_transaction(tx_hash, target_address)
    elif network == "ERC20":
        return await check_ethereum_transaction(tx_hash, target_address)
    elif network == "BEP20":
        return await check_bsc_transaction(tx_hash, target_address)
    else:
        return {
            "success": False,
            "error": f"Неподдерживаемая сеть: {network}"
        }


def save_transaction_hash(user: str, transaction_hash: str, wallet_address: str, status: str) -> bool:
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист4')

        row = [
            user,
            transaction_hash,
            wallet_address,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status
        ]

        sheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"✅ Запись добавлена: {row}")
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
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
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
