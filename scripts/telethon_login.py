import asyncio
import logging
import sys
import ssl
import socket
from pathlib import Path

# Настройка детального логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Импортируем конфиг
try:
    import config
except Exception as e:
    logger.error(f"❌ Не удалось импортировать config.py: {e}")
    sys.exit(1)

# Проверяем API-данные
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
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

async def main():
    logger.info("=== 📲 Авторизация в Telegram через Telethon ===")
    logger.info(f" API ID: {config.TELEGRAM_API_ID}")
    logger.debug(f"🔑 API Hash: {config.TELEGRAM_API_HASH[:10]}...")
    
    # Создаем клиент с дополнительными параметрами для Windows
    client = TelegramClient(
        str(SESSION_FILE), 
        config.TELEGRAM_API_ID, 
        config.TELEGRAM_API_HASH,
        # Дополнительные параметры для Windows
        connection_retries=5,
        retry_delay=1,
        timeout=30,
        # Принудительно используем IPv4
        use_ipv6=False
    )

    try:
        logger.info("🔌 Подключаемся к Telegram...")
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info("✅ Авторизация прошла успешно!")
            logger.info(f"👋 Зашли как: {me.first_name} (@{me.username})")
            logger.info(f"📞 Номер телефона: {me.phone}")
            logger.info(f"✅ Сессия сохранена в: {SESSION_FILE}")
        else:
            logger.info("📱 Требуется авторизация...")
            print(" Введите номер телефона (включая код страны, например: +380501234567):")
            
            try:
                phone = input().strip()
                logger.info(f"📱 Отправляем код на номер: {phone}")
                
                # Отправляем код
                await client.send_code_request(phone)
                print("✅ Код отправлен! Проверьте Telegram.")
                print("🔢 Введите код из Telegram:")
                
                code = input().strip()
                logger.info("🔐 Пытаемся войти с кодом...")
                
                try:
                    await client.sign_in(phone, code)
                    logger.info("✅ Вход выполнен успешно!")
                    
                    me = await client.get_me()
                    logger.info(f"👋 Добро пожаловать, {me.first_name}!")
                    logger.info(f"✅ Сессия сохранена в: {SESSION_FILE}")
                    
                except SessionPasswordNeededError:
                    print("🔒 Введите пароль двухфакторной аутентификации:")
                    password = input().strip()
                    await client.sign_in(password=password)
                    logger.info("✅ Вход с 2FA выполнен успешно!")
                    
                except PhoneCodeInvalidError:
                    logger.error("❌ Неверный код! Попробуйте снова.")
                    return
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при авторизации: {e}", exc_info=True)
                print(f"Ошибка: {e}")
                
    except Exception as e:
        logger.exception("❌ Произошла ошибка при подключении к Telegram")
        print(f"Ошибка: {e}")
        
        # Дополнительная диагностика для Windows
        logger.info("\n🔍 Диагностика для Windows:")
        logger.info("1. Проверьте, не блокирует ли антивирус соединения")
        logger.info("2. Попробуйте отключить Windows Defender Firewall")
        logger.info("3. Проверьте настройки прокси в системе")
        logger.info("4. Убедитесь, что время на компьютере синхронизировано")
        
    finally:
        try:
            await client.disconnect()
        except:
            pass

if __name__ == "__main__":
    # Проверяем версию Python и SSL
    logger.info(f"🐍 Python версия: {sys.version}")
    logger.info(f"🔒 SSL версия: {ssl.OPENSSL_VERSION}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ Прервано пользователем")
    except Exception as e:
        logger.exception("❌ Критическая ошибка")
        print(f"Критическая ошибка: {e}")