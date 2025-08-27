import re
import easyocr
import cv2
import numpy as np
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

class TransactionImageParser:
    """
    Класс для парсинга изображений транзакций и извлечения хешей
    """
    
    def __init__(self):
        """Инициализация OCR читателя"""
        try:
            # Инициализируем EasyOCR с поддержкой русского и английского языков
            self.reader = easyocr.Reader(['ru', 'en'], gpu=False)
            logger.info("✅ OCR читатель инициализирован успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OCR: {e}")
            self.reader = None
    
    def preprocess_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Предобработка изображения для улучшения качества OCR
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Обработанное изображение или None при ошибке
        """
        try:
            # Читаем изображение
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"❌ Не удалось прочитать изображение: {image_path}")
                return None
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Увеличиваем контраст
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Убираем шум
            denoised = cv2.fastNlMeansDenoising(enhanced)
            
            # Бинаризация для улучшения читаемости текста
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
            
        except Exception as e:
            logger.error(f"❌ Ошибка предобработки изображения: {e}")
            return None
    
    def extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Извлекает текст из изображения
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Извлеченный текст или None
        """
        if self.reader is None:
            logger.error("❌ OCR читатель не инициализирован")
            return None
        
        try:
            logger.info(f"🔍 Начинаем извлечение текста из изображения: {image_path}")
            
            # Пробуем сначала с оригинальным изображением
            results = self.reader.readtext(image_path)
            logger.info(f"🔍 OCR результаты (всего блоков: {len(results)})")
            
            # Объединяем все найденные тексты с оригиналом, сохраняя порядок
            extracted_text = ""
            # Сортируем результаты по позиции (сверху вниз, слева направо)
            sorted_results = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))
            
            for (bbox, text, confidence) in sorted_results:
                logger.info(f"📍 Блок текста: '{text}' (уверенность: {confidence:.2f})")
                if confidence > 0.1:
                    extracted_text += text + "\n"
            
            if extracted_text:
                logger.info(f"✅ Извлеченный текст:\n{extracted_text}")
                return extracted_text
            
            logger.warning("⚠️ Текст не извлечен, пробуем с предобработкой")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения текста: {e}")
            return None
    
    def extract_transaction_hash(self, text: str) -> Optional[str]:
        """
        Извлекает хеш транзакции из текста
        
        Args:
            text: Текст для поиска хеша
            
        Returns:
            Найденный хеш или None
        """
        if not text:
            logger.warning("⚠️ Текст пустой для поиска хеша")
            return None
            
        logger.info("🔍 Начинаем поиск хеша в тексте:")
        logger.info(f"Исходный текст:\n{text}")
        
        # Разбиваем текст на строки
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Ищем строки, которые идут после TxID
        try:
            txid_index = next(i for i, line in enumerate(lines) if 'TxID' in line)
            potential_hash_lines = []
            
            # Собираем следующие строки после TxID, которые содержат только hex символы
            # Проверяем больше строк, чтобы не пропустить первую часть хеша
            for i in range(txid_index + 1, min(txid_index + 6, len(lines))):
                line = lines[i]
                # Извлекаем только hex символы
                hex_only = ''.join(c for c in line if c in '0123456789ABCDEFabcdef')
                if hex_only and len(hex_only) >= 8:  # Снижаем минимальную длину для первой строки
                    potential_hash_lines.append(hex_only)
                    logger.info(f"Найдена строка с hex после TxID (строка {i}): {hex_only}")
                elif hex_only:
                    logger.info(f"Строка {i} содержит hex, но слишком короткая: {hex_only}")
            
            if potential_hash_lines:
                # Объединяем все найденные части
                combined_hash = ''.join(potential_hash_lines)
                logger.info(f"Объединенный хеш: {combined_hash}")
                
                # Проверяем длину
                if len(combined_hash) >= 64:
                    result = combined_hash[:64]
                    logger.info(f"✅ Итоговый хеш (64 символа): {result}")
                    return result
                else:
                    logger.warning(f"⚠️ Полученный хеш слишком короткий: {combined_hash}")
                    return combined_hash
                    
        except (StopIteration, ValueError) as e:
            logger.info("TxID не найден в тексте, пробуем другие методы")
        
        # Если не нашли через TxID, ищем просто строки с hex символами
        hex_lines = []
        for line in lines:
            # Очищаем строку от всего кроме hex символов
            hex_only = ''.join(c for c in line if c in '0123456789ABCDEFabcdef')
            if hex_only and len(hex_only) >= 10:
                hex_lines.append(hex_only)
                logger.info(f"Найдена строка с hex: {hex_only}")
        
        if hex_lines:
            combined_hash = ''.join(hex_lines)
            logger.info(f"Объединенные hex строки: {combined_hash}")
            
            if len(combined_hash) >= 64:
                result = combined_hash[:64]
                logger.info(f"✅ Итоговый хеш (64 символа): {result}")
                return result
            else:
                logger.warning(f"⚠️ Недостаточно символов для полного хеша: {combined_hash}")
                return combined_hash
        
        logger.warning("❌ Хеш не найден")
        return None
    
    def extract_transaction_details(self, image_path: str) -> dict:
        """
        Извлекает детали транзакции из изображения
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Словарь с деталями транзакции
        """
        result = {
            'success': False,
            'hash': None,
            'amount': None,
            'network': None,
            'address': None,
            'raw_text': None,
            'error': None
        }
        
        try:
            logger.info(f"🔍 Начинаем извлечение деталей из изображения: {image_path}")
            
            # Извлекаем текст
            text = self.extract_text_from_image(image_path)
            if not text:
                result['error'] = "Не удалось извлечь текст из изображения"
                logger.error("❌ Не удалось извлечь текст из изображения")
                return result
            
            logger.info(f"✅ Текст извлечен: {text[:200]}...")
            result['raw_text'] = text
            
            # Анализируем структуру текста
            structure_analysis = self.analyze_text_structure(text)
            if structure_analysis:
                logger.info(f"🔍 Анализ структуры: {structure_analysis['total_hex_chars']} hex символов в {structure_analysis['total_lines']} строках")
            
            # Ищем хеш транзакции
            tx_hash = self.extract_transaction_hash(text)
            if tx_hash:
                result['hash'] = tx_hash
                result['success'] = True
                logger.info(f"✅ Хеш найден: {tx_hash}")
                
                # Дополнительная проверка валидности хеша
                from utils.validators import is_valid_tx_hash
                network = result.get('network', 'TRC20')  # По умолчанию TRC20
                
                # Проверяем длину хеша
                if len(tx_hash) < 16
                    logger.warning(f"⚠️ Хеш слишком короткий: {tx_hash} (длина: {len(tx_hash)})")
                    result['error'] = f"Хеш слишком короткий: {tx_hash} (длина: {len(tx_hash)})"
                    result['success'] = False
                elif len(tx_hash) < 32:
                    logger.warning(f"⚠️ Хеш короткий, но может быть валидным: {tx_hash} (длина: {len(tx_hash)})")
                    # Для коротких хешей все равно считаем успехом, но предупреждаем
                    result['success'] = True
                elif len(tx_hash) == 64:
                    logger.info(f"✅ Найден полный хеш длиной 64 символа: {tx_hash}")
                    result['success'] = True
                    # Добавляем дополнительную проверку на наличие невидимых символов
                    tx_hash = tx_hash.strip()
                    if len(tx_hash.encode('utf-8')) != 64:
                        logger.warning(f"⚠️ Хеш содержит невидимые символы, очищаем: {tx_hash}")
                        tx_hash = ''.join(c for c in tx_hash if c.isprintable())
                    result['hash'] = tx_hash
                elif is_valid_tx_hash(tx_hash, network):
                    logger.info(f"✅ Хеш прошел валидацию для сети {network}")
                else:
                    logger.warning(f"⚠️ Хеш не прошел валидацию для сети {network}: {tx_hash}")
                    # Попробуем определить сеть по формату хеша
                    if tx_hash.startswith('0x'):
                        result['network'] = 'ERC20'
                        logger.info(f"🔍 Автоопределение сети: ERC20 (хеш с 0x)")
                    else:
                        result['network'] = 'TRC20'
                        logger.info(f"🔍 Автоопределение сети: TRC20 (хеш без 0x)")
            else:
                logger.warning("⚠️ Хеш не найден")
                result['error'] = "Хеш транзакции не найден в изображении"
            
            # Ищем сумму (паттерн для USDT, USD, UAH)
            amount_pattern = r'(\d+(?:\.\d+)?)\s*(USDT|USD|UAH|₴|\$)'
            amount_match = re.search(amount_pattern, text, re.IGNORECASE)
            if amount_match:
                result['amount'] = f"{amount_match.group(1)} {amount_match.group(2)}"
                logger.info(f"✅ Сумма найдена: {result['amount']}")
            
            # Определяем сеть по ключевым словам (если еще не определена)
            if not result.get('network'):
                if 'TRX' in text.upper() or 'TRC20' in text.upper():
                    result['network'] = 'TRC20'
                    logger.info("✅ Сеть определена по ключевым словам: TRC20")
                elif 'ERC20' in text.upper() or 'ETH' in text.upper():
                    result['network'] = 'ERC20'
                    logger.info("✅ Сеть определена по ключевым словам: ERC20")
                elif 'BSC' in text.upper() or 'BNB' in text.upper():
                    result['network'] = 'BSC'
                    logger.info("✅ Сеть определена по ключевым словам: BSC")
                else:
                    # По умолчанию TRC20
                    result['network'] = 'TRC20'
                    logger.info("✅ Сеть по умолчанию: TRC20")
            
            # Ищем адрес кошелька (паттерн для различных сетей)
            address_patterns = [
                r'\bT[A-Za-z0-9]{33}\b',  # TRX адрес
                r'\b0x[A-Fa-f0-9]{40}\b',  # ETH/BSC адрес
                r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'  # BTC адрес
            ]
            
            for pattern in address_patterns:
                addresses = re.findall(pattern, text)
                if addresses:
                    result['address'] = addresses[0]
                    logger.info(f"✅ Адрес найден: {result['address']}")
                    break
            
            logger.info(f"✅ Детали транзакции извлечены: {result}")
            
        except Exception as e:
            result['error'] = f"Ошибка при обработке изображения: {str(e)}"
            logger.error(f"❌ Ошибка извлечения деталей: {e}")
        
        return result

    def assemble_hash_from_parts(self, text: str) -> Optional[str]:
        """
        Собирает хеш транзакции из частей, если OCR разбил его на куски
        
        Args:
            text: Текст для поиска частей хеша
            
        Returns:
            Собранный хеш или None
        """
        try:
            logger.info("🔍 Начинаем сборку хеша из частей")
            
            # Ищем все hex символы в тексте
            all_hex_chars = re.findall(r'[A-Fa-f0-9]', text)
            logger.info(f"🔍 Найдено hex символов: {len(all_hex_chars)}")
            
            if len(all_hex_chars) >= 64:
                # Собираем полный хеш из всех hex символов
                assembled = ''.join(all_hex_chars)
                # Берем первые 64 символа (полный хеш)
                full_hash = assembled[:64]
                logger.info(f"🔍 Собран полный хеш из {len(all_hex_chars)} символов: {full_hash}")
                return full_hash
            
            # Если символов меньше 64, ищем hex последовательности
            hex_parts = re.findall(r'\b[A-Fa-f0-9]{2,}\b', text)
            logger.info(f"🔍 Найдены hex части: {hex_parts}")
            
            if not hex_parts:
                return None
            
            # Фильтруем части, которые могут быть частью хеша
            potential_parts = []
            for part in hex_parts:
                # Проверяем, что часть содержит только hex символы
                if re.match(r'^[A-Fa-f0-9]+$', part):
                    potential_parts.append(part)
            
            logger.info(f"🔍 Потенциальные части хеша: {potential_parts}")
            
            if not potential_parts:
                return None
            
            # Сортируем по длине (самые длинные первыми)
            potential_parts.sort(key=len, reverse=True)
            
            # Пробуем собрать хеш из самых длинных частей
            for i, part in enumerate(potential_parts):
                if len(part) >= 64:  # Если часть уже полная
                    logger.info(f"🔍 Найдена полная часть: {part}")
                    return part
                
                # Пробуем объединить с другими частями
                for j, other_part in enumerate(potential_parts):
                    if i != j:
                        combined = part + other_part
                        if len(combined) >= 64 and re.match(r'^[A-Fa-f0-9]+$', combined):
                            # Берем первые 64 символа
                            full_hash = combined[:64]
                            logger.info(f"🔍 Объединены части {part} + {other_part} = {full_hash}")
                            return full_hash
            
            # Если не удалось собрать из двух частей, пробуем собрать из всех частей
            logger.info("🔍 Пробуем собрать хеш из всех частей")
            all_parts_combined = ''.join(potential_parts)
            if len(all_parts_combined) >= 64 and re.match(r'^[A-Fa-f0-9]+$', all_parts_combined):
                full_hash = all_parts_combined[:64]
                logger.info(f"🔍 Собран хеш из всех частей: {full_hash}")
                return full_hash
            
            # Если не удалось собрать полный хеш, берем самую длинную часть
            longest_part = potential_parts[0]
            if len(longest_part) >= 32:  # Минимальная длина для хеша
                logger.info(f"🔍 Используем самую длинную часть: {longest_part}")
                return longest_part
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при сборке хеша из частей: {e}")
            return None

    def extract_hash_with_position_awareness(self, text: str) -> Optional[str]:
        """
        Извлекает хеш с учетом позиции символов в тексте
        
        Args:
            text: Текст для поиска хеша
            
        Returns:
            Найденный хеш или None
        """
        try:
            logger.info("🔍 Извлечение хеша с учетом позиции")
            
            # Ищем все hex символы с их позициями
            hex_chars_with_pos = []
            for i, char in enumerate(text):
                if char in '0123456789ABCDEFabcdef':
                    hex_chars_with_pos.append((i, char))
            
            logger.info(f"🔍 Найдено {len(hex_chars_with_pos)} hex символов")
            
            if len(hex_chars_with_pos) >= 64:
                # Собираем символы в правильном порядке
                hex_chars_with_pos.sort(key=lambda x: x[0])  # Сортируем по позиции
                assembled = ''.join(char for _, char in hex_chars_with_pos)
                
                # Берем первые 64 символа
                full_hash = assembled[:64]
                logger.info(f"🔍 Собран хеш с учетом позиции: {full_hash}")
                return full_hash
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при извлечении хеша с учетом позиции: {e}")
            return None

    def extract_hash_from_multiple_lines(self, text: str) -> Optional[str]:
        """
        Извлекает хеш из нескольких строк, собирая их в правильном порядке
        
        Args:
            text: Текст для поиска хеша
            
        Returns:
            Найденный хеш или None
        """
        try:
            logger.info("🔍 Извлечение хеша из нескольких строк")
            
            # Разбиваем текст на строки и очищаем их
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            logger.info(f"🔍 Найдено {len(lines)} строк")
            
            # Ищем последовательные строки с hex символами
            hex_lines = []
            for line in lines:
                # Очищаем строку от всех символов кроме hex
                hex_only = ''.join(c for c in line if c in '0123456789ABCDEFabcdef')
                if hex_only:
                    hex_lines.append(hex_only)
                    logger.info(f"🔍 Найдена строка с hex: {hex_only}")
            
            if not hex_lines:
                return None
            
            # Объединяем все hex строки
            combined_hash = ''.join(hex_lines)
            logger.info(f"🔍 Объединенный хеш: {combined_hash}")
            
            # Если получили достаточно символов для полного хеша
            if len(combined_hash) >= 64:
                full_hash = combined_hash[:64]
                logger.info(f"✅ Собран полный хеш из строк: {full_hash}")
                return full_hash
            
            # Если не получили полный хеш, но есть значительная часть
            if len(combined_hash) >= 32:
                logger.info(f"⚠️ Собран неполный хеш: {combined_hash}")
                return combined_hash
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при извлечении хеша из строк: {e}")
            return None

    def analyze_text_structure(self, text: str) -> dict:
        """
        Анализирует структуру текста для поиска хешей
        
        Args:
            text: Текст для анализа
            
        Returns:
            Словарь с информацией о структуре
        """
        try:
            logger.info("🔍 Анализ структуры текста")
            
            # Разбиваем на строки
            lines = text.split('\n')
            logger.info(f"🔍 Найдено {len(lines)} строк")
            
            # Анализируем каждую строку
            line_analysis = []
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Ищем hex символы в строке
                hex_chars = re.findall(r'[A-Fa-f0-9]', line)
                hex_count = len(hex_chars)
                
                # Ищем hex последовательности
                hex_sequences = re.findall(r'\b[A-Fa-f0-9]{4,}\b', line)
                
                analysis = {
                    'line_number': i,
                    'line_text': line,
                    'hex_chars_count': hex_count,
                    'hex_sequences': hex_sequences,
                    'hex_sequences_count': len(hex_sequences)
                }
                
                line_analysis.append(analysis)
                logger.info(f"🔍 Строка {i}: {hex_count} hex символов, {len(hex_sequences)} последовательностей")
            
            # Ищем строки с наибольшим количеством hex символов
            hex_rich_lines = [line for line in line_analysis if line['hex_chars_count'] >= 16]
            
            result = {
                'total_lines': len(lines),
                'line_analysis': line_analysis,
                'hex_rich_lines': hex_rich_lines,
                'total_hex_chars': sum(line['hex_chars_count'] for line in line_analysis)
            }
            
            logger.info(f"🔍 Всего hex символов: {result['total_hex_chars']}")
            logger.info(f"🔍 Строк с hex: {len(hex_rich_lines)}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе структуры текста: {e}")
            return {}

# Создаем глобальный экземпляр парсера
transaction_parser = TransactionImageParser() 