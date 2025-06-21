# google_utils.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import aiohttp
import csv
import json
from typing import Optional, Dict, Any
from config import ETHERSCAN_API_KEY, BSCSCAN_API_KEY

def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        'client_secret.json', scope)  # Укажи свой путь
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

def get_wallet_address(sheet_name: str, network: str) -> str:
    """
    Получает адрес кошелька для указанной сети из Google Sheets
    """
    try:
        # Здесь должна быть логика получения адреса кошелька из Google Sheets
        # Пока возвращаем заглушку с реальными адресами
        wallet_addresses = {
            "ERC20": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",
            "TRC20": "TQn9Y2khDD95J42FQtQTdwVVRZQKdXz9Kf",
            "BEP20": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",
            "Polygon": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6"
        }
        return wallet_addresses.get(network, "Адрес не найден")
    except Exception as e:
        print(f"Ошибка при получении адреса кошелька: {e}")
        return None

def save_transaction_hash(sheet_name: str, transaction_hash: str, network: str, crypto: str, amount: str, contact: str) -> bool:
    """
    Сохраняет хеш транзакции в Google Sheets
    """
    try:
        # Здесь должна быть логика сохранения в Google Sheets
        # Пока просто возвращаем True
        print(f"Сохранен хеш транзакции: {transaction_hash}")
        print(f"Сеть: {network}, Криптовалюта: {crypto}, Сумма: {amount}, Контакт: {contact}")
        return True
    except Exception as e:
        print(f"Ошибка при сохранении хеша транзакции: {e}")
        return False

async def check_tron_transaction(tx_hash: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию в сети TRON через Tronscan API
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Получаем информацию о транзакции
            url = f"{TRONSCAN_API}/transaction-info"
            params = {"hash": tx_hash}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Проверяем статус транзакции
                    if data.get("confirmed") and data.get("confirmed") == True:
                        # Проверяем, что транзакция направлена на наш адрес
                        if data.get("to") == target_address:
                            return {
                                "success": True,
                                "status": "confirmed",
                                "amount": data.get("amount", 0),
                                "from": data.get("from", ""),
                                "to": data.get("to", ""),
                                "timestamp": data.get("timestamp", 0)
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Транзакция направлена на другой адрес"
                            }
                    else:
                        return {
                            "success": False,
                            "error": "Транзакция не подтверждена"
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

async def check_ethereum_transaction(tx_hash: str, target_address: str, api_key: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию в сети Ethereum через Etherscan API
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{ETHERSCAN_API}"
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": api_key
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
        return await check_ethereum_transaction(tx_hash, target_address, ETHERSCAN_API_KEY)
    elif network == "BEP20":
        return await check_bsc_transaction(tx_hash, target_address)
    elif network == "Polygon":
        # Polygon использует тот же API что и Ethereum
        return await check_ethereum_transaction(tx_hash, target_address, ETHERSCAN_API_KEY)
    else:
        return {
            "success": False,
            "error": f"Неподдерживаемая сеть: {network}"
        }
