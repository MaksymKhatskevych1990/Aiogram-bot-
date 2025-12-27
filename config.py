import logging
import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные из .env (для локальной разработки)
load_dotenv()

logger = logging.getLogger(__name__)

# Настройка уровня логирования в зависимости от окружения
environment = os.getenv('ENVIRONMENT', 'development')
if environment == 'production':
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)

# Чтобы логи выводились в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Конфигурация бота
# TOKEN теперь передается через аргументы командной строки в main.py
# Оставляем для обратной совместимости со старым кодом
TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN')

# Глобальная переменная для хранения текущего токена бота (устанавливается в main.py)
_current_bot_token: Optional[str] = None

def set_current_bot_token(token: str):
    """Устанавливает текущий токен бота (вызывается из main.py)"""
    global _current_bot_token
    _current_bot_token = token

def get_current_bot_token() -> Optional[str]:
    """Получает текущий токен бота"""
    global _current_bot_token
    return _current_bot_token or TOKEN
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# URL для получения курсов валют
CSV_URL = os.getenv('CSV_URL')

LOGO_PATH = os.getenv('LOGO_PATH')
# URL для получения адресов кошельков
WALLET_SHEET_URL = os.getenv('WALLET_SHEET_URL')

# API ключи для проверки транзакций
TRONSCAN_API_KEY = os.getenv('TRONSCAN_API_KEY')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
BSCSCAN_API_KEY = os.getenv('BSCSCAN_API_KEY')
# TRONSCAN не требует API ключа для базовых запросов

TRC20_CONFIRMATIONS = int(os.getenv('TRC20_CONFIRMATIONS', '12'))
# По умолчанию используем TronGrid (если не указан другой API)
TRONSCAN_API = os.getenv('TRONSCAN_API', 'https://api.trongrid.io')
ERC20_CONFIRMATIONS = int(os.getenv('ERC20_CONFIRMATIONS', '12'))
ETHERSCAN_API = os.getenv('ETHERSCAN_API', 'https://api.etherscan.io/api')

# Контракты токенов для валидации
USDT_TRC20_CONTRACT = os.getenv('USDT_TRC20_CONTRACT', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')
USDT_ERC20_CONTRACT = os.getenv('USDT_ERC20_CONTRACT', '0xdac17f958d2ee523a2206206994597c13d831ec7').lower()

# Redis Configuration для Railway
REDIS_URL = os.getenv('REDIS_URL')
REDIS_DB_FSM = os.getenv('REDIS_DB_FSM')
REDIS_BACKEND_DB = os.getenv('REDIS_BACKEND_DB')
REDIS_KEY_PREFIX_ERC = os.getenv('REDIS_KEY_PREFIX_ERC')
REDIS_KEY_PREFIX_TRC = os.getenv('REDIS_KEY_PREFIX_TRC')
# Парсим Redis URL для совместимости с существующим кодом
if REDIS_URL:
    try:
        # Формат: redis://default:password@host:port
        if REDIS_URL.startswith('redis://'):
            parts = REDIS_URL.replace('redis://', '').split('@')
            if len(parts) == 2:
                auth_part = parts[0]
                host_part = parts[1]
                
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                    REDISPASSWORD = password
                else:
                    REDISPASSWORD = None
                
                if ':' in host_part:
                    host, port = host_part.split(':', 1)
                    REDISHOST = host
                    REDISPORT = int(port)
                else:
                    REDISHOST = host_part
                    REDISPORT = 6379
            else:
                REDISHOST = 'localhost'
                REDISPORT = 6379
                REDISPASSWORD = None
        else:
            REDISHOST = 'localhost'
            REDISPORT = 6379
            REDISPASSWORD = None
    except Exception as e:
        logger.warning(f"Ошибка парсинга Redis URL: {e}")
        REDISHOST = 'localhost'
        REDISPORT = 6379
        REDISPASSWORD = None
else:
    REDISHOST = os.getenv('REDISHOST', 'localhost')
    REDISPORT = int(os.getenv('REDISPORT', 6379))
    REDISPASSWORD = os.getenv('REDISPASSWORD')

REDIS_DB = int(os.getenv('REDIS_DB', 1))
REDIS_KEY_PREFIX = os.getenv('REDIS_KEY_PREFIX', 'bot')

# ID чата администратора для заявок
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')  # Замените на реальный ID админ-группы

# Telethon (userbot)
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')            # укажи свой api_id с my.telegram.org
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')         # укажи свой api_hash с my.telegram.org
TELETHON_SESSION = os.getenv('TELETHON_SESSION')  # имя файла сессии (создастся после логина)

# Backend API для интеграции
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
BOT_API_KEY = os.getenv('BOT_API_KEY', '')  # API ключ для аутентификации в backend

GOOGLE_CREDENTIALS  = {
    "type": os.getenv("GOOGLE_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CRT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
}