#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы калькулятора комиссий
"""

from utils.commission_calculator import commission_calculator

def test_commission_calculator():
    """Тестирует калькулятор комиссий с различными суммами"""
    
    print("🧪 Тестирование калькулятора комиссий\n")
    
    # Тестовые суммы для USDT → USD
    test_amounts_usdt_to_usd = [50, 500, 1500, 3000, 6000]
    
    print("📊 Тест USDT → USD (Обналичивание):")
    print("-" * 50)
    
    for amount in test_amounts_usdt_to_usd:
        result = commission_calculator.calculate_commission('USDT_to_USD', amount)
        if result['success']:
            print(f"Сумма: {amount} USDT")
            print(f"Тип комиссии: {result['commission_type']}")
            print(f"Значение комиссии: {result['commission_value']}")
            print(f"Комиссия: {result['commission_amount']:.2f} USD")
            print(f"Итого: {result['final_amount']:.2f} USD")
            print(f"Менеджер: {'Да' if result['manager_required'] else 'Нет'}")
            print("-" * 30)
        else:
            print(f"Ошибка для суммы {amount}: {result['error']}")
    
    print("\n📊 Тест USD → USDT (Покупка крипты):")
    print("-" * 50)
    
    # Тестовые суммы для USD → USDT
    test_amounts_usd_to_usdt = [50, 500, 1500, 3000, 6000]
    
    for amount in test_amounts_usd_to_usdt:
        result = commission_calculator.calculate_commission('USD_to_USDT', amount)
        if result['success']:
            print(f"Сумма: {amount} USD")
            print(f"Тип комиссии: {result['commission_type']}")
            print(f"Значение комиссии: {result['commission_value']}")
            print(f"Комиссия: {result['commission_amount']:.2f} USD")
            print(f"Итого: {result['final_amount']:.2f} USDT")
            print(f"Менеджер: {'Да' if result['manager_required'] else 'Нет'}")
            print("-" * 30)
        else:
            print(f"Ошибка для суммы {amount}: {result['error']}")
    
    # Тест получения курса обмена
    print("\n💱 Тест получения курса обмена:")
    print("-" * 30)
    
    rate = commission_calculator.get_exchange_rate()
    if rate:
        print(f"Текущий курс USDT/USD: {rate}")
    else:
        print("Курс не найден или ошибка получения")

if __name__ == "__main__":
    test_commission_calculator() 