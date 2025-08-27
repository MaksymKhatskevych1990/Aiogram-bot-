#!/usr/bin/env python3
"""
Тестовый скрипт для проверки извлечения хешей из нескольких строк
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.transaction_image_parser import TransactionImageParser
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_multiline_hash_extraction():
    """Тестирует извлечение хешей из нескольких строк"""
    
    parser = TransactionImageParser()
    
    # Тестовые случаи с многострочными хешами
    test_cases = [
        # Хеш разбитый на 3 строки (как в вашем случае)
        """TxID: 75f22599f2eda2a50d723f028
1234567890abcdef1234567890abcdef
1234567890abcdef1234567890abcdef""",
        
        # Хеш с разными символами между строками
        """Transaction Hash:
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678
End of transaction""",
        
        # Хеш разбитый неравномерно
        """Hash: a1b2c3d4e5f6789012345678901234567890abcdef
1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef""",
        
        # Хеш с лишним текстом
        """Some text before
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678
Some text after""",
        
        # Хеш с вашим примером
        """75f22599f2eda2a50d723f028
1234567890abcdef1234567890abcdef
1234567890abcdef1234567890abcdef""",
    ]
    
    print("🧪 Тестирование извлечения хешей из нескольких строк")
    print("=" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}:")
        print(f"Входной текст:\n{test_text}")
        
        # Анализируем структуру
        structure = parser.analyze_text_structure(test_text)
        if structure:
            print(f"🔍 Анализ структуры:")
            print(f"   Всего строк: {structure['total_lines']}")
            print(f"   Всего hex символов: {structure['total_hex_chars']}")
            print(f"   Строк с hex: {len(structure['hex_rich_lines'])}")
        
        # Извлекаем хеш из нескольких строк
        hash_found = parser.extract_hash_from_multiple_lines(test_text)
        
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

def test_your_specific_case():
    """Тестирует ваш конкретный случай"""
    
    parser = TransactionImageParser()
    
    # Ваш конкретный случай
    your_text = """75f22599f2eda2a50d723f028
1234567890abcdef1234567890abcdef
1234567890abcdef1234567890abcdef"""
    
    print("\n🧪 Тестирование вашего конкретного случая")
    print("=" * 60)
    print(f"Входной текст:\n{your_text}")
    
    # Анализируем структуру
    structure = parser.analyze_text_structure(your_text)
    if structure:
        print(f"🔍 Анализ структуры:")
        print(f"   Всего строк: {structure['total_lines']}")
        print(f"   Всего hex символов: {structure['total_hex_chars']}")
        for line in structure['line_analysis']:
            print(f"   Строка {line['line_number']}: {line['hex_chars_count']} hex символов")
    
    # Извлекаем хеш
    hash_found = parser.extract_transaction_hash(your_text)
    
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
    test_multiline_hash_extraction()
    test_your_specific_case()
    print("\n✅ Тестирование завершено!") 