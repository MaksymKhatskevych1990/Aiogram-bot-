import aiohttp
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
from utils.decode_etc20 import decode_erc20_input
from utils.extract_hash_in_url import extract_tx_hash


USDT_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # уже в lowercase


def validate_ethereum_address(address: str) -> bool:
    """Проверяет корректность Ethereum адреса."""
    if not address:
        return False
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address.lower()))


async def check_ethereum_transaction(user_input: str, target_address: str) -> Dict[str, Any]:
    """
    Проверяет транзакцию ERC20 USDT в сети Ethereum.
    """
    # Валидация входных данных
    if not user_input or not target_address:
        return {"success": False, "error": "Необходимо указать хеш транзакции и целевой адрес"}
    
    if not validate_ethereum_address(target_address):
        return {"success": False, "error": "Некорректный формат целевого адреса"}
    
    tx_hash: Optional[str] = extract_tx_hash(user_input)
    if not tx_hash:
        return {"success": False, "error": "Введите корректный хеш или ссылку на транзакцию"}

    target_address = target_address.lower()
    url = "https://api.etherscan.io/api"

    try:
        async with aiohttp.ClientSession() as session:
            # Получаем данные транзакции
            params_tx = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": ETHERSCAN_API_KEY
            }
            async with session.get(url, params=params_tx) as resp_tx:
                if resp_tx.status != 200:
                    return {"success": False, "error": f"Ошибка API: {resp_tx.status}"}

                data = await resp_tx.json()
                tx_data = data.get("result")
                logger.info("ETH tx data: %s", tx_data)

                if not tx_data:
                    return {"success": False, "error": "Транзакция не найдена"}

                if not tx_data.get("blockNumber"):
                    return {"success": False, "error": "Транзакция ещё не подтверждена (нет blockNumber)"}

                if tx_data.get("to", "").lower() != USDT_CONTRACT:
                    return {"success": False, "error": "Транзакция не относится к контракту USDT"}

                # Декодируем входные данные
                decoded = decode_erc20_input(tx_data.get("input", ""))
                if not decoded:
                    return {"success": False, "error": "Не удалось декодировать данные транзакции"}

                decoded_to = decoded["to"].lower()
                logger.info("Проверка целевого адреса: decoded_to=%s, target_address=%s", decoded_to, target_address)

                if decoded_to != target_address:
                    return {"success": False, "error": "Токены отправлены на другой адрес"}

            await asyncio.sleep(0.6)

            # Получаем последний номер блока
            params_latest = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": ETHERSCAN_API_KEY
            }
            async with session.get(url, params=params_latest) as resp_latest:
                latest_data = await resp_latest.json()
                latest_block_hex = latest_data.get("result")
                if not latest_block_hex:
                    return {"success": False, "error": "Не удалось получить номер последнего блока"}
                latest_block = int(latest_block_hex, 16)

            await asyncio.sleep(0.6)

            tx_block = int(tx_data.get("blockNumber"), 16)
            confirmations = latest_block - tx_block + 1

            if confirmations < ERC20_CONFIRMATIONS:
                return {"success": False, "error": f"Недостаточно подтверждений: {confirmations}/{ERC20_CONFIRMATIONS}"}

            # Получаем данные блока для timestamp
            params_block = {
                "module": "proxy",
                "action": "eth_getBlockByNumber",
                "tag": tx_data.get("blockNumber"),
                "boolean": "true",
                "apikey": ETHERSCAN_API_KEY
            }
            async with session.get(url, params=params_block) as resp_block:
                block_data = await resp_block.json()
                block = block_data.get("result")
                logger.info("ETH block data: %s", block)

                if not block or "timestamp" not in block:
                    return {"success": False, "error": "Не удалось получить timestamp блока"}

                timestamp = int(block["timestamp"], 16)
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

            amount = decoded["amount"] / 10**6  # USDT имеет 6 знаков после запятой

            return {
                "success": True,
                "status": "confirmed",
                "amount_raw": decoded["amount"],
                "amount": amount,
                "from": tx_data.get("from", "").lower(),
                "to": decoded_to,
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "confirmations": confirmations
            }

    except Exception as e:
        logger.exception("Ошибка при проверке Ethereum транзакции")
        return {"success": False, "error": f"Ошибка проверки транзакции: {str(e)}"}
