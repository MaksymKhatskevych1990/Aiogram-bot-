import asyncio
import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import PhoneCodeInvalidError, PhoneNumberInvalidError, SessionPasswordNeededError

# Настройка детального логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загружаем переменные из .env
load_dotenv()

async def debug_login():
    print("=== 🔍 Детальная диагностика авторизации Telegram ===")
    
    # Получаем API ключи
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:10]}...")
    
    if not api_id or not api_hash:
        print("❌ API ключи не найдены!")
        return
    
    try:
        api_id_int = int(api_id)
    except ValueError:
        print("❌ API ID не является числом!")
        return
    
    print(f"✅ API ID корректно преобразован: {api_id_int}")
    
    # Создаем клиент с детальным логированием
    client = TelegramClient('debug_session', api_id_int, api_hash)
    
    try:
        print("🔌 Подключаемся к Telegram...")
        await client.connect()
        print("✅ Подключение установлено")
        
        if await client.is_user_authorized():
            print("✅ Уже авторизован!")
            me = await client.get_me()
            print(f"👤 Пользователь: {me.first_name} (@{me.username})")
            print(f"�� Телефон: {me.phone}")
        else:
            print("📱 Требуется авторизация...")
            print("Введите номер телефона (например: +380916231565):")
            phone = input().strip()
            
            print(f"📤 Отправляем запрос кода для номера: {phone}")
            
            try:
                # Отправляем запрос кода с детальным логированием
                result = await client.send_code_request(phone)
                print(f"✅ Запрос кода отправлен успешно!")
                print(f"📋 Тип кода: {result.type}")
                print(f"📋 Длина кода: {result.length}")
                print(f"📋 Таймаут: {result.timeout} секунд")
                
                # Ждем немного
                print("⏳ Ждем 10 секунд для получения кода...")
                await asyncio.sleep(10)
                
                print("Введите полученный код (или 'resend' для повторной отправки):")
                code = input().strip()
                
                if code.lower() == 'resend':
                    print("📤 Повторно отправляем код...")
                    await client.send_code_request(phone)
                    print("Введите новый код:")
                    code = input().strip()
                
                try:
                    await client.sign_in(phone, code)
                    print("✅ Авторизация успешна!")
                    me = await client.get_me()
                    print(f"👤 Пользователь: {me.first_name} (@{me.username})")
                    print(f"�� Телефон: {me.phone}")
                except PhoneCodeInvalidError:
                    print("❌ Неверный код! Попробуйте еще раз.")
                except SessionPasswordNeededError:
                    print("🔐 Требуется двухфакторная аутентификация!")
                    print("Введите пароль двухфакторной аутентификации:")
                    password = input().strip()
                    try:
                        await client.sign_in(password=password)
                        print("✅ Двухфакторная аутентификация успешна!")
                    except Exception as e:
                        print(f"❌ Ошибка двухфакторной аутентификации: {e}")
                except Exception as e:
                    print(f"❌ Ошибка при вводе кода: {e}")
                    
            except PhoneNumberInvalidError:
                print("❌ Неверный номер телефона!")
            except Exception as e:
                print(f"❌ Ошибка при отправке кода: {e}")
                print(f"Тип ошибки: {type(e).__name__}")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
    finally:
        await client.disconnect()
        print("�� Соединение закрыто")

if __name__ == "__main__":
    asyncio.run(debug_login())