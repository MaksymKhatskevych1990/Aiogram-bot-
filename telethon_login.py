import re
import sys
import redis
import json
import logging
import importlib

from typing import Dict, Optional, Tuple
from aiogram import Bot
from telethon import TelegramClient
import sys
from pathlib import Path
from config import REDISHOST, REDISPASSWORD, REDISPORT, REDIS_DB, REDIS_KEY_PREFIX
import config  # твой конфиг с TELEGRAM_API_ID и TELEGRAM_API_HASH

# 📌 Путь к файлу сессии Telethon — создаём сразу при загрузке модуля
BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "rates_session.session"

logger = logging.getLogger(__name__)

class ChannelRatesParser:
    def __init__(self, bot: Bot, channel_username: str = "@obmenvalut13"):
        self.bot = bot
        self.channel_username = channel_username

        # Redis
        self.redis_client = redis.Redis(
            host=REDISHOST,
            password=REDISPASSWORD,
            port=REDISPORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_timeout=3
        )
        self.cache_ttl = 300  # 5 минут кэш

        # Подгружаем API-ключи из config.py
        cfg = importlib.import_module("config")
        self.tg_api_id = getattr(cfg, "TELEGRAM_API_ID", 0)
        self.tg_api_hash = getattr(cfg, "TELEGRAM_API_HASH", "")

        # Telethon клиент
        self.telethon_client = TelegramClient(str(SESSION_FILE), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)


    async def get_latest_rates(self) -> Dict[str, Dict]:
        """Возвращает все последние курсы"""
        try:
            cached_rates = self.redis_client.get('currency_rates')
            if cached_rates:
                return json.loads(cached_rates)

            rates = await self._parse_channel_rates()
            if rates:
                self.redis_client.setex('currency_rates', self.cache_ttl, json.dumps(rates))
                return rates

            return self._get_default_rates()
        except Exception:
            logger.exception("Ошибка при получении курсов")
            return self._get_default_rates()

    async def _parse_channel_rates(self) -> Optional[Dict[str, Dict]]:
        if not self.telethon_client:
            logger.error("Telethon не настроен (нет api_id/api_hash в config.py)")
            return None
        try:
            await self.telethon_client.connect()
            if not await self.telethon_client.is_user_authorized():
                logger.error("Telethon не авторизован. Запусти scripts/telethon_login.py один раз.")
                return None

            entity = await self.telethon_client.get_entity(self.channel_username)
            async for msg in self.telethon_client.iter_messages(entity, limit=10):
                text = (msg.message or "") if hasattr(msg, "message") else ""
                if not text:
                    continue
                rates = self._extract_rates_from_text(text)
                if rates:
                    logger.info(f"Курсы получены из истории канала: {rates}")
                    return rates
            return None
        except Exception:
            logger.exception("Telethon error")
            return None
        finally:
            try:
                await self.telethon_client.disconnect()
            except Exception:
                pass

    def _extract_rates_from_text(self, text: str) -> Optional[Dict[str, Dict]]:
        """Парсит сообщение с курсами валют"""
        t = text.replace(',', '.').replace('—', '-').replace('–', '-')
        rates: Dict[str, Dict] = {}

        pattern = re.compile(
            r"(USD|EUR|GBP|PLN)\s+([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)(?:\s+([^\n]+))?",
            re.IGNORECASE
        )

        for match in pattern.finditer(t):
            cur = match.group(1).upper()
            buy = float(match.group(2))
            sell = float(match.group(3))
            label = (match.group(4) or "").strip().lower()

            pair_key = f"{cur}-UAH"
            if pair_key not in rates:
                rates[pair_key] = {}

            if "1000" in label or "опт" in label or "від" in label:
                rates[pair_key]["wholesale"] = {"buy": buy, "sell": sell}
            else:
                rates[pair_key]["retail"] = {"buy": buy, "sell": sell}

        return rates if rates else None

    def _get_default_rates(self) -> Dict[str, Dict]:
        """Курсы по умолчанию"""
        return {
            'USD-UAH': {'retail': {'buy': 38.50, 'sell': 38.80}},
            'EUR-UAH': {'retail': {'buy': 41.20, 'sell': 41.50}},
            'GBP-UAH': {'retail': {'buy': 48.80, 'sell': 49.20}},
            'PLN-UAH': {'retail': {'buy': 9.80, 'sell': 9.95}}
        }

    def get_specific_rate(self, currency_pair: str) -> Optional[Tuple[float, float]]:
        """Возвращает retail курс по конкретной паре"""
        try:
            rates = self.redis_client.get('currency_rates')
            if rates:
                rd = json.loads(rates).get(currency_pair, {}).get("retail")
                if rd:
                    return rd['buy'], rd['sell']
            return None
        except Exception:
            logger.exception(f"Ошибка при получении курса {currency_pair}")
            return None

    async def force_refresh_rates(self) -> Dict[str, Dict]:
        """Очистка кэша и повторное получение курсов"""
        self.redis_client.delete('currency_rates')
        return await self.get_latest_rates()


# Глобальный экземпляр
channel_rates_parser = None
