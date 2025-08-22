# 🔧 Настройка Redis для бота

## 📋 Требования

Для корректной работы бота необходимо настроить подключение к Redis серверу.

## 🚀 Настройка

### 1. Создайте файл `.env` в корневой папке проекта:

```bash
# Redis Configuration
REDIS_URL=redis://default:pAnOMsKGoqPWMrIPncxfDgtcIWlTqXYu@redis-s59x.railway.internal:6379

# Bot Configuration
TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id_here

# Google API Configuration
GOOGLE_API_KEY=your_google_api_key_here

# Other configurations...
CSV_URL=your_csv_url_here
LOGO_PATH=path_to_logo_here
```

### 2. Убедитесь, что переменная `REDIS_URL` содержит правильный URL вашего Redis сервера

### 3. Перезапустите бота

## 🔍 Проверка подключения

При запуске бота в консоли должно появиться:
- ✅ `Redis подключен успешно` - если подключение работает
- ❌ `Ошибка подключения к Redis: [описание ошибки]` - если есть проблемы

## 🆘 Fallback механизм

Если Redis недоступен, бот автоматически:
1. Попытается использовать файл `request_counter.txt` для хранения счетчика заявок
2. В крайнем случае использует временную метку как номер заявки

## 📝 Примечания

- Файл `.env` добавлен в `.gitignore` для безопасности
- Счетчик заявок начинается с 1
- Номера заявок уникальны для каждого экземпляра бота 