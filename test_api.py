import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

print(f"TELEGRAM_API_ID: {api_id}")
print(f"TELEGRAM_API_HASH: {api_hash}")

if api_id and api_hash:
    print("✅ API ключи найдены")
    print(f"API ID тип: {type(api_id)}")
    print(f"API Hash тип: {type(api_hash)}")
    
    # Проверяем, что API ID является числом
    try:
        api_id_int = int(api_id)
        print(f"✅ API ID корректно преобразуется в число: {api_id_int}")
    except ValueError:
        print("❌ API ID не является числом!")
else:
    print("❌ API ключи не найдены или пустые")
    print("Проверьте файл .env и убедитесь, что он содержит:")
    print("TELEGRAM_API_ID=ваш_api_id")
    print("TELEGRAM_API_HASH=ваш_api_hash")