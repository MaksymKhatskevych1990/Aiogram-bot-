import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

# Загружаем переменные из .env
load_dotenv()

async def test_connection():
    print("=== 🔍 Тестирование подключения к Telegram ===")
    
    # Получаем API ключи
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:10]}...")  # Показываем только первые 10 символов
    
    if not api_id or not api_hash:
        print("❌ API ключи не найдены!")
        return
    
    # Преобразуем API ID в число
    try:
        api_id_int = int(api_id)
    except ValueError:
        print("❌ API ID не является числом!")
        return
    
    print(f"✅ API ID корректно преобразован: {api_id_int}")
    
    # Создаем клиент
    client = TelegramClient('test_session', api_id_int, api_hash)
    
    try:
        print("🔌 Подключаемся к Telegram...")
        await client.connect()
        
        if await client.is_user_authorized():
            print("✅ Уже авторизован!")
            me = await client.get_me()
            print(f"👤 Пользователь: {me.first_name} (@{me.username})")
            print(f"�� Телефон: {me.phone}")
        else:
            print("📱 Требуется авторизация...")
            print("Введите номер телефона (например: +380916231565):")
            phone = input().strip()
            
            print("📤 Отправляем код...")
            await client.send_code_request(phone)
            
            print("✅ Код отправлен! Проверьте Telegram.")
            print("Введите полученный код:")
            code = input().strip()
            
            try:
                await client.sign_in(phone, code)
                print("✅ Авторизация успешна!")
                me = await client.get_me()
                print(f"👤 Пользователь: {me.first_name} (@{me.username})")
            except Exception as e:
                print(f"❌ Ошибка при вводе кода: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_connection())