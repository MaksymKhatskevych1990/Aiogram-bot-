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
    test_hash = "c8977b5ee2c45ba1e089a13dd22ea9fdb7947aa9dff7cea78e858d6926cbc8a6"
    
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
    test_hash = "0x137623f1d02708ef35b330d575ed5505a7506d0b73f28ad604618426cdde601d"
    
    # Проверяем транзакцию
    result = await verify_transaction(test_hash, "ERC20", wallet_address)
    
    print(f"🔍 Результат проверки: {result}")
    
    if result.get("success"):
        print("✅ Транзакция подтверждена!")
    else:
        print(f"❌ Ошибка: {result.get('error')}")

async def test_wallet_addresses():
    """Тест получения адресов кошельков"""
    print("\n🧪 Тестирование получения адресов кошельков...")
    
    networks = ["TRC20", "ERC20", "BEP20", "Polygon"]
    
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
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    asyncio.run(main()) 