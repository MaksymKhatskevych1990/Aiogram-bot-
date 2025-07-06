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


async def check_tron_transaction(tx_hash: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию в сети TRON через Tronscan API
    """
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TRONSCAN_API}/transaction-info"
            params = {"hash": tx_hash}

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}

                data = await response.json()

                if data.get("confirmed") is not True:
                    return {"success": False, "error": "Транзакция не подтверждена"}

                # Проверка количества подтверждений
                confirmations = data.get("confirmations", 0)
                if confirmations < TRC20_CONFIRMATIONS:
                    return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{TRC20_CONFIRMATIONS}"}

                if data.get("contractRet") != "SUCCESS":
                    return {"success": False, "error": f"Ошибка исполнения: {data.get('contractRet')}"}

                transfers = data.get("trc20TransferInfo", [])
                if not transfers:
                    return {"success": False, "error": "Нет TRC20-переводов в транзакции"}

                transfer = transfers[0]
                logger.info("Получен transfer: %s", transfer)

                if transfer["to_address"] != target_address:
                    return {"success": False, "error": "Транзакция направлена на другой адрес"}


                # """Нужно уточнить что делать если пользователь перевел не USDT, а какой то другой токен"""

                # if transfer["contract_address"] != USDT_CONTRACT:
                #     return {"success": False, "error": "Неверный токен. Ожидается USDT (TRC20)"}
                
                """------------------------------------------------------------------------------------"""

                raw_value = int(transfer["amount_str"])
                decimals = int(transfer["decimals"])
                value = raw_value / 10**decimals

                timestamp = data.get("timestamp", 0)
                dt = datetime.datetime.fromtimestamp(timestamp / 1000)

                return {
                    "success": True,
                    "status": "confirmed",
                    "amount": value,
                    "from": transfer.get("from_address", ""),
                    "to": transfer.get("to_address", ""),
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "confirmations": confirmations
                }

    except Exception as e:
        return {"success": False, "error": f"Ошибка проверки транзакции: {str(e)}"}

async def check_ethereum_transaction(tx_hash: str, target_address: str, api_key: str) -> Dict[str, Any]:
    """
    Проверяет ERC20-транзакцию через etherscan API, извлекая to/amount из input.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = ETHERSCAN_API
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": ETHERSCAN_API_KEY
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Ошибка API: {response.status}"}

                data = await response.json()
                

                tx_data = data.get("result")
                block_number = tx_data.get("blockNumber")


                logger.info("Получен data ------ ETH: %s", data)
                if not tx_data:
                    return {"success": False, "error": "Транзакция не найдена"}

                # Проверка, что это вызов контракта USDT
                if tx_data.get("to", "").lower() != "0xdac17f958d2ee523a2206206994597c13d831ec7":
                    return {"success": False, "error": "Это не транзакция USDT"}
                
                decoded = decode_erc20_input(tx_data["input"])
                logger.info("Получен decoded ------ ETH: %s", decoded)
                if not decoded:
                    return {"success": False, "error": "Невозможно декодировать входные данные"}
                logger.info("Получен decoded ------ ETH: %s", decoded["to"].lower())
                # Сравнение адресов в нижнем регистре
                if decoded["to"].lower() != target_address.lower():
                    return {"success": False, "error": "Токены отправлены на другой адрес"}
                # Проверка количества подтверждений
                # Получаем текущий номер блока
                params_latest = {
                    "module": "proxy",
                    "action": "eth_blockNumber",
                    "apikey": api_key
                }
                async with session.get(ETHERSCAN_API, params=params_latest) as resp_latest:
                    latest_block_data = await resp_latest.json()
                    latest_block_hex = latest_block_data.get("result")
                    if not latest_block_hex:
                        return {"success": False, "error": "Не удалось получить номер последнего блока"}
                    latest_block = int(latest_block_hex, 16)
                tx_block = int(block_number, 16)
                confirmations = latest_block - tx_block + 1
                if confirmations < ERC20_CONFIRMATIONS:
                    return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}"}
                params_block = {
                    "module": "proxy",
                    "action": "eth_getBlockByNumber",
                    "tag": block_number,
                    "boolean": "true",
                    "apikey": api_key
                }
                async with session.get(ETHERSCAN_API, params=params_block) as resp_block:
                    block_response = await resp_block.json()
                    block_data = block_response.get("result")
                    timestamp = block_data.get("timestamp")  # в hex

                    # Переводим в int
                    ts_int = int(timestamp, 16)
                    dt = datetime.datetime.fromtimestamp(ts_int / 1000)
                return {
                    "success": True,
                    "status": "confirmed",
                    "amount_raw": decoded["amount"],
                    "amount": decoded["amount"] / 10**6,  # USDT имеет 6 знаков
                    "from": tx_data.get("from", ""),
                    "to": decoded["to"],
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "confirmations": confirmations
                }


    except Exception as e:
        return {"success": False, "error": f"Ошибка: {str(e)}"}

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
        return await check_ethereum_transaction(tx_hash, target_address, ETHERSCAN_API)
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
