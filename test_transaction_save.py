#!/usr/bin/env python3
"""
Тест для проверки сохранения транзакции в Google Sheets
"""

import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google_utils import save_transaction_hash, is_duplicate_transaction, update_transaction_status

def test_transaction_save():
    """Тестирует сохранение транзакции ERC20"""
    
    # Тестовые данные для транзакции ERC20
    tx_hash = "0xbf84ff89f8faf73189657f96799a251c3775645b49ccee16208c25a9a1fba377"
    network = "ERC20"
    username = 1036774169
    target_address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    timestamp = "2025-01-27 12:00:00"
    now = "2025-01-27 12:00:00"
    status = "confirmed"
    amount = "50"
    error = ""
    
    print(f"🧪 Тестирование сохранения транзакции ERC20...")
    print(f"📋 Хеш: {tx_hash}")
    print(f"🌐 Сеть: {network}")
    print(f"👤 Пользователь: {username}")
    print(f"💰 Сумма: {amount}")
    
    # Проверяем, является ли транзакция дубликатом
    print(f"\n🔍 Проверка дубликатов...")
    is_duplicate = is_duplicate_transaction(tx_hash)
    print(f"📊 Дубликат: {'Да' if is_duplicate else 'Нет'}")
    
    if is_duplicate:
        print("⚠️ Транзакция уже существует в таблице!")
        return
    
    # Подготавливаем параметры для сохранения
    google_params = [
        username,      # 0: Id пользователя
        tx_hash,       # 1: tx_hash
        target_address, # 2: target_address
        timestamp,     # 3: timestamp
        now,           # 4: now
        status,        # 5: status
        amount,        # 6: amount
        error          # 7: error
    ]
    
    print(f"\n💾 Сохранение транзакции...")
    result = save_transaction_hash(google_params, network)
    
    if result:
        print("✅ Транзакция успешно сохранена!")
        
        # Тестируем обновление статуса
        print(f"\n🔄 Тестирование обновления статуса...")
        google_update_params = {
            "status": ["confirmed", 9],  # Колонка I (9-я колонка)
            "date_confirmation": [now, 8]  # Колонка H (8-я колонка)
        }
        
        update_result = update_transaction_status(tx_hash, google_update_params, network)
        if update_result:
            print("✅ Статус транзакции обновлен!")
        else:
            print("❌ Ошибка при обновлении статуса")
    else:
        print("❌ Ошибка при сохранении транзакции")

if __name__ == "__main__":
    test_transaction_save()

