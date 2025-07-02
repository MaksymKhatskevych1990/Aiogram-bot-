#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функционала проверки транзакций
"""

import asyncio
from google_utils import verify_transaction, get_wallet_address

async def test_tron_transaction():
    """Тест проверки TRC20 транзакции"""
    print("🧪 Тестирование TRC20 транзакции...")
    
    # Получаем адрес кошелька
    wallet_address = get_wallet_address("Лист3", "TRC20")
    print(f"📧 Адрес кошелька: {wallet_address}")
    
    # Тестовый хеш (несуществующий)
    test_hash = "f5d8e9c1b2a3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9"

    
    # Проверяем транзакцию
    result = await verify_transaction(test_hash, "TRC20", wallet_address)
    
    print(f"🔍 Результат проверки: {result}")
    
    if result.get("success"):
        print("✅ Транзакция подтверждена!")
    else:
        print(f"❌ Ошибка: {result.get('error')}")

async def test_ethereum_transaction():
    """Тест проверки ERC20 транзакции"""
    print("\n🧪 Тестирование ERC20 транзакции...")
    
    # Получаем адрес кошелька
    wallet_address = get_wallet_address("Лист3", "ERC20")
    print(f"📧 Адрес кошелька: {wallet_address}")
    
    # Тестовый хеш (несуществующий)
    test_hash = "0x125d640e70d17b217c071b0c79c6ecd2fd8c70c371fec9355fc16fba9c7ddc3b"

    
    # Проверяем транзакцию
    result = await verify_transaction(test_hash, "ERC20", wallet_address)
    
    print(f"🔍 Результат проверки: {result}")
    
    if result.get("success"):
        print("✅ Транзакция подтверждена!")
    else:
        print(f"❌ Ошибка: {result.get('error')}")

async def test_bep20_transaction():
    """Тест проверки BEP20 транзакции"""
    print("\n🧪 Тестирование BEP20 транзакции...")
    
    # Получаем адрес кошелька
    wallet_address = get_wallet_address("Лист3", "BEP20")
    print(f"📧 Адрес кошелька: {wallet_address}")
    
    # Тестовый хеш (несуществующий)
    test_hash = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdef"
    
    # Проверяем транзакцию
    result = await verify_transaction(test_hash, "BEP20", wallet_address)
    
    print(f"🔍 Результат проверки: {result}")
    
    if result.get("success"):
        print("✅ Транзакция подтверждена!")
    else:
        print(f"❌ Ошибка: {result.get('error')}")

async def test_wallet_addresses():
    """Тест получения адресов кошельков"""
    print("\n🧪 Тестирование получения адресов кошельков...")
    
    networks = ["TRC20", "ERC20", "BEP20"]
    
    for network in networks:
        address = get_wallet_address("Лист3", network)
        print(f"🌐 {network}: {address}")

async def main():
    """Главная функция тестирования"""
    print("🚀 Запуск тестов проверки транзакций...\n")
    
    # Тестируем получение адресов
    await test_wallet_addresses()
    
    # Тестируем проверку транзакций
    await test_tron_transaction()
    await test_ethereum_transaction()
    await test_bep20_transaction()
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    asyncio.run(main()) 