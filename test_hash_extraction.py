#!/usr/bin/env python3
"""
Тестовый скрипт для проверки извлечения хешей из текста
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.transaction_image_parser import TransactionImageParser
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_hash_extraction():
    """Тестирует извлечение хешей из различных текстов"""
    
    parser = TransactionImageParser()
    
    # Тестовые случаи
    test_cases = [
        # Полный хеш TRC20
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Полный хеш ERC20
        "Transaction Hash: 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        
        # Разбитый хеш (как может быть распознан OCR)
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш с лишними символами
        "Hash: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Короткий хеш (для тестирования)
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef",
        
        # Хеш разбитый на части
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef 1234567890abcdef12345678",
        
        # Текст с несколькими hex строками
        "Some text with hex: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678 and another: 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        
        # Текст с ключевыми словами
        "Transaction ID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Текст с русскими ключевыми словами
        "Хеш транзакции: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш разбитый на очень маленькие части (симуляция OCR)
        "a1b2 c3d4 e5f6 7890 1234 5678 9012 3456 7890 abcd ef12 3456 7890 abcd ef12 3456 7890",
        
        # Хеш с разными символами между частями
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш с цифрами и буквами вперемешку
        "Hash: 1a2b3c4d5e6f789012345678901234567890abcdef1234567890abcdef12345678",
    ]
    
    print("🧪 Тестирование извлечения хешей из текста")
    print("=" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}:")
        print(f"Входной текст: {test_text}")
        
        # Извлекаем хеш
        hash_found = parser.extract_transaction_hash(test_text)
        
        if hash_found:
            print(f"✅ Найден хеш: {hash_found}")
            print(f"   Длина: {len(hash_found)}")
            
            # Проверяем валидность
            from utils.validators import is_valid_tx_hash
            if hash_found.startswith('0x'):
                network = 'ERC20'
            else:
                network = 'TRC20'
            
            is_valid = is_valid_tx_hash(hash_found, network)
            print(f"   Валидность для {network}: {'✅' if is_valid else '❌'}")
        else:
            print("❌ Хеш не найден")
        
        print("-" * 40)

def test_hash_assembly():
    """Тестирует сборку хешей из частей"""
    
    parser = TransactionImageParser()
    
    # Тестовые случаи с разбитыми хешами
    test_cases = [
        # Хеш разбитый на маленькие части
        "a1b2 c3d4 e5f6 7890 1234 5678 9012 3456 7890 abcd ef12 3456 7890 abcd ef12 3456 7890",
        
        # Хеш с лишними символами
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш разбитый неравномерно
        "a1b2c3d4e5f6789012345678901234567890abcdef 1234567890abcdef12345678",
        
        # Только hex символы
        "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш разбитый на очень маленькие части (как может быть с OCR)
        "a1 b2 c3 d4 e5 f6 78 90 12 34 56 78 90 12 34 56 78 90 ab cd ef 12 34 56 78 90 ab cd ef 12 34 56 78 90",
        
        # Хеш с разными символами между частями
        "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш с цифрами и буквами вперемешку
        "1a2b3c4d5e6f789012345678901234567890abcdef1234567890abcdef12345678",
    ]
    
    print("\n🧪 Тестирование сборки хешей из частей")
    print("=" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}:")
        print(f"Входной текст: {test_text}")
        
        # Собираем хеш из частей
        hash_found = parser.assemble_hash_from_parts(test_text)
        
        if hash_found:
            print(f"✅ Собран хеш: {hash_found}")
            print(f"   Длина: {len(hash_found)}")
        else:
            print("❌ Хеш не собран")
        
        print("-" * 40)

def test_position_aware_extraction():
    """Тестирует извлечение хеша с учетом позиции символов"""
    
    parser = TransactionImageParser()
    
    # Тестовые случаи с разбитыми хешами
    test_cases = [
        # Хеш разбитый на части с разными символами между ними
        "TxID: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
        
        # Хеш с лишними символами
        "Some text a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678 more text",
        
        # Хеш разбитый неравномерно
        "a1b2c3d4e5f6789012345678901234567890abcdef 1234567890abcdef12345678",
        
        # Хеш с цифрами и буквами вперемешку
        "1a2b3c4d5e6f789012345678901234567890abcdef1234567890abcdef12345678",
    ]
    
    print("\n🧪 Тестирование извлечения хеша с учетом позиции")
    print("=" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}:")
        print(f"Входной текст: {test_text}")
        
        # Извлекаем хеш с учетом позиции
        hash_found = parser.extract_hash_with_position_awareness(test_text)
        
        if hash_found:
            print(f"✅ Найден хеш: {hash_found}")
            print(f"   Длина: {len(hash_found)}")
        else:
            print("❌ Хеш не найден")
        
        print("-" * 40)

if __name__ == "__main__":
    test_hash_extraction()
    test_hash_assembly()
    test_position_aware_extraction()
    print("\n✅ Тестирование завершено!") 