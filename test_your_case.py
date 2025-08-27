#!/usr/bin/env python3
"""
Тестовый скрипт для вашего конкретного случая с хешем из 3 строк
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.transaction_image_parser import TransactionImageParser
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_your_specific_case():
    """Тестирует ваш конкретный случай с хешем из 3 строк"""
    
    parser = TransactionImageParser()
    
    # Ваш конкретный случай - хеш из 3 строк
    your_text = """6f92e0bad6177be2efc3a4d41
75f22599f2eda2a50d723f028c
d65b9e65c9d78"""
    
    print("🧪 Тестирование вашего конкретного случая")
    print("=" * 60)
    print(f"Входной текст:\n{your_text}")
    
    # Анализируем структуру
    structure = parser.analyze_text_structure(your_text)
    if structure:
        print(f"\n🔍 Анализ структуры:")
        print(f"   Всего строк: {structure['total_lines']}")
        print(f"   Всего hex символов: {structure['total_hex_chars']}")
        for line in structure['line_analysis']:
            print(f"   Строка {line['line_number']}: {line['hex_chars_count']} hex символов - '{line['line_text']}'")
    
    # Извлекаем хеш из нескольких строк
    print(f"\n🔍 Извлечение хеша из нескольких строк:")
    hash_found = parser.extract_hash_from_multiple_lines(your_text)
    
    if hash_found:
        print(f"✅ Найден хеш: {hash_found}")
        print(f"   Длина: {len(hash_found)}")
        
        # Проверяем валидность
        from utils.validators import is_valid_tx_hash
        is_valid = is_valid_tx_hash(hash_found, 'TRC20')
        print(f"   Валидность для TRC20: {'✅' if is_valid else '❌'}")
    else:
        print("❌ Хеш не найден")
    
    # Извлекаем хеш общим методом
    print(f"\n🔍 Извлечение хеша общим методом:")
    hash_found_general = parser.extract_transaction_hash(your_text)
    
    if hash_found_general:
        print(f"✅ Найден хеш: {hash_found_general}")
        print(f"   Длина: {len(hash_found_general)}")
        
        # Проверяем валидность
        from utils.validators import is_valid_tx_hash
        is_valid = is_valid_tx_hash(hash_found_general, 'TRC20')
        print(f"   Валидность для TRC20: {'✅' if is_valid else '❌'}")
    else:
        print("❌ Хеш не найден")
    
    print("-" * 40)

def test_with_txid_label():
    """Тестирует случай с меткой TxID"""
    
    parser = TransactionImageParser()
    
    # Случай с меткой TxID
    text_with_label = """TxID: 6f92e0bad6177be2efc3a4d41
75f22599f2eda2a50d723f028c
d65b9e65c9d78"""
    
    print("\n🧪 Тестирование с меткой TxID")
    print("=" * 60)
    print(f"Входной текст:\n{text_with_label}")
    
    # Извлекаем хеш
    hash_found = parser.extract_transaction_hash(text_with_label)
    
    if hash_found:
        print(f"✅ Найден хеш: {hash_found}")
        print(f"   Длина: {len(hash_found)}")
        
        # Проверяем валидность
        from utils.validators import is_valid_tx_hash
        is_valid = is_valid_tx_hash(hash_found, 'TRC20')
        print(f"   Валидность для TRC20: {'✅' if is_valid else '❌'}")
    else:
        print("❌ Хеш не найден")
    
    print("-" * 40)

if __name__ == "__main__":
    test_your_specific_case()
    test_with_txid_label()
    print("\n✅ Тестирование завершено!") 