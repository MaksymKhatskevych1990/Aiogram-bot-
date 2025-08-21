#!/usr/bin/env python3
"""
Тестовый скрипт для проверки генерации QR кода
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.generate_qr_code import generate_wallet_qr
from localization import get_message

async def test_qr_generation():
    """Тестируем генерацию QR кода"""
    print("🧪 Тестируем генерацию QR кода...")
    
    # Тестовые данные
    test_address = "TQn9Y2khDD95J42FQtQTdwVVRZzVLJkkvj"
    test_network = "TRC20"
    test_lang = "ru"
    
    print(f"📝 Адрес: {test_address}")
    print(f"🌐 Сеть: {test_network}")
    print(f"🌍 Язык: {test_lang}")
    
    # Проверяем локализацию
    try:
        qr_caption = get_message("qr_caption", test_lang, address=test_address)
        print(f"✅ Локализация работает: {qr_caption}")
    except Exception as e:
        print(f"❌ Ошибка локализации: {e}")
        return
    
    # Проверяем, что файл логотипа существует
    logo_path = "img/logo-qr.png"
    if os.path.exists(logo_path):
        print(f"✅ Логотип найден: {logo_path}")
    else:
        print(f"❌ Логотип не найден: {logo_path}")
        return
    
    print("✅ Все проверки пройдены успешно!")
    print("💡 Теперь можно тестировать бота")

if __name__ == "__main__":
    asyncio.run(test_qr_generation()) 