# scripts/telethon_login.py

import asyncio
import logging
import sys
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем корневую директорию проекта (на уровень выше, чем scripts/)
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Проверяем, существует ли config.py
CONFIG_PATH = BASE_DIR / "config.py"
if not CONFIG_PATH.exists():
    logger.error(f"❌ Файл config.py не найден по пути: {CONFIG_PATH}")
    logger.error("Убедитесь, что config.py существует и содержит TELEGRAM_API_ID и TELEGRAM_API_HASH")
    sys.exit(1)

# Импортируем конфиг
try:
    import config
except Exception as e:
    logger.error("❌ Не удалось импортировать config.py")
    logger.error(f"Ошибка: {e}")
    sys.exit(1)

# Проверяем наличие API-данных
if not hasattr(config, "TELEGRAM_API_ID") or not hasattr(config, "TELEGRAM_API_HASH"):
    logger.error("❌ В config.py должны быть определены: TELEGRAM_API_ID и TELEGRAM_API_HASH")
    sys.exit(1)

if config.TELEGRAM_API_ID == 0 or not config.TELEGRAM_API_HASH:
    logger.error("❌ TELEGRAM_API_ID или TELEGRAM_API_HASH не заданы в config.py")
    sys.exit(1)

# Путь к файлу сессии
SESSION_FILE = BASE_DIR / "rates_session.session"
logger.info(f"📁 Файл сессии будет сохранён: {SESSION_FILE}")

from telethon import TelegramClient


async def main():
    print("=== 📲 Авторизация в Telegram через Telethon ===")
    client = TelegramClient(str(SESSION_FILE), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)

    try:
        await client.start()

        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info("✅ Авторизация прошла успешно!")
            print(f"👋 Зашли как: {me.first_name} (@{me.username})")
            print(f"📞 Номер телефона: {me.phone}")
            print(f"")
            print(f"✅ Сессия сохранена в: {SESSION_FILE}")
            print(f"ℹ️  Теперь можно запускать бота — он будет использовать эту сессию.")
        else:
            logger.error("❌ Не удалось авторизоваться. Попробуйте снова.")
            print("Возможно, вы ввели неправильный код или номер.")
    except Exception as e:
        logger.exception("❌ Произошла ошибка при подключении к Telegram")
        print(f"Ошибка: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())