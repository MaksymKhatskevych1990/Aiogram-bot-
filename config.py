import logging
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Чтобы логи выводились в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

#Конфигурация бота
TOKEN = os.getenv('TOKEN')
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

TRC20_CONFIRMATIONS = os.getenv('TRC20_CONFIRMATIONS')
TRONSCAN_API = os.getenv('TRONSCAN_API')
ERC20_CONFIRMATIONS = os.getenv('ERC20_CONFIRMATIONS')

# Настройки Google Sheets API (заполните своими данными)
GOOGLE_CREDENTIALS = {
    "type": "service_account",
    "project_id": "your-project-id",
    "private_key_id": "your-private-key-id",
    "private_key": "your-private-key",
    "client_email": "your-client-email",
    "client_id": "your-client-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "your-cert-url"
}


# ID чата администратора для заявок
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')  # Замените на реальный ID админ-группы

# Telethon (userbot)
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')            # укажи свой api_id с my.telegram.org
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')         # укажи свой api_hash с my.telegram.org
TELETHON_SESSION = os.getenv('TELETHON_SESSION')  # имя файла сессии (создастся после логина)