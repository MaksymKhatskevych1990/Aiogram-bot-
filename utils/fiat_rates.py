import aiohttp
import csv
import importlib
from typing import Optional, Tuple, Dict
from config import CSV_URL

# Динамически получаем парсер из utils.channel_rates (инициализируется в main.py)
try:
    channel_module = importlib.import_module("utils.channel_rates")
except Exception:
    channel_module = None


def _get_channel_parser():
    if channel_module is None:
        return None
    return getattr(channel_module, "channel_rates_parser", None)


async def get_usd_uah_rates(wholesale: bool = False) -> Tuple[Optional[float], Optional[float]]:
    """
    Возвращает (buy, sell) по паре USD-UAH.
    :param wholesale: Если True — вернуть оптовый курс (від 1000), иначе роздріб.
    """
    parser = _get_channel_parser()
    if parser:
        try:
            rates = await parser.get_latest_rates()
            usd_data = rates.get("USD-UAH", {})
            key = "wholesale" if wholesale else "retail"
            if key in usd_data:
                r = usd_data[key]
                return r["buy"], r["sell"]
        except Exception as e:
            print(f"Ошибка при получении курса USD из канала: {e}")

    # Fallback на CSV (только retail)
    return await _get_usd_from_csv()

from config import ETHERSCAN_API_KEY, ERC20_CONFIRMATIONS, logger
async def _get_usd_from_csv() -> Tuple[float, float]:
    try:
        async with aiohttp.ClientSession() as session:
            session_id = hex(id(session))
            logger.info(f"[fiat_rates] ===================================Created ClientSession {session_id}")
            async with session.get(CSV_URL) as resp:
                if resp.status != 200:
                    print(f"CSV недоступен, статус {resp.status}")
                    return 38.50, 38.80
                text_data = await resp.text()
                rows = list(csv.reader(text_data.splitlines()))
                for row in rows[1:]:
                    if len(row) < 3:
                        continue
                    name = row[0].strip().upper()
                    if name == "USD":
                        try:
                            buy = float(row[1].replace(",", "."))
                            sell = float(row[2].replace(",", "."))
                            return buy, sell
                        except Exception:
                            return 38.50, 38.80
    except Exception as e:
        print(f"Ошибка при получении USD из CSV: {e}")
    return 38.50, 38.80


async def get_all_currency_rates(wholesale: bool = False) -> Dict[str, Dict[str, float]]:
    """
    Возвращает все курсы в формате {"USD-UAH": {"buy": .., "sell": ..}, ...}
    :param wholesale: Если True — вернуть оптовые курсы (від 1000), иначе роздріб.
    """
    parser = _get_channel_parser()
    if parser:
        try:
            raw_rates = await parser.get_latest_rates()
            rates: Dict[str, Dict[str, float]] = {}
            key = "wholesale" if wholesale else "retail"
            for pair, data in raw_rates.items():
                if key in data:
                    rates[pair] = data[key]
            if rates:
                return rates
        except Exception as e:
            print(f"Ошибка при получении курсов из канала: {e}")

    # Fallback на CSV (только retail)
    return await _get_all_from_csv()


async def _get_all_from_csv() -> Dict[str, Dict[str, float]]:
    rates: Dict[str, Dict[str, float]] = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CSV_URL) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"CSV недоступен, статус {resp.status}")
                text_data = await resp.text()
                rows = list(csv.reader(text_data.splitlines()))
                for row in rows[1:]:
                    if len(row) >= 3:
                        try:
                            cur = row[0].strip().upper()
                            buy = float(row[1].replace(",", "."))
                            sell = float(row[2].replace(",", "."))
                        except Exception:
                            continue
                        if cur in ("USD", "EUR", "GBP", "PLN"):
                            rates[f"{cur}-UAH"] = {"buy": buy, "sell": sell}
    except Exception as e:
        print(f"Ошибка при получении курсов из CSV: {e}")

    if not rates:
        rates = {
            "USD-UAH": {"buy": 38.50, "sell": 38.80},
            "EUR-UAH": {"buy": 41.20, "sell": 41.50},
            "GBP-UAH": {"buy": 48.80, "sell": 49.20},
            "PLN-UAH": {"buy": 9.80, "sell": 9.95},
        }
    return rates
