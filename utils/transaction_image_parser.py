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
            Извлеченный текст или None при ошибке
        """
        if self.reader is None:
            logger.error("❌ OCR читатель не инициализирован")
            return None
        
        try:
            logger.info(f"🔍 Начинаем извлечение текста из изображения: {image_path}")
            
            # Пробуем сначала с оригинальным изображением
            results = self.reader.readtext(image_path)
            logger.info(f"🔍 OCR результаты (оригинал): {len(results)} блоков текста")
            
            if not results:
                logger.info("🔍 OCR не дал результатов с оригиналом, пробуем предобработку")
                # Если не получилось, пробуем с предобработанным изображением
                processed_image = self.preprocess_image(image_path)
                if processed_image is not None:
                    results = self.reader.readtext(processed_image)
                    logger.info(f"🔍 OCR результаты (предобработка): {len(results)} блоков текста")
            
            # Объединяем все найденные тексты
            extracted_text = ""
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Фильтруем по уверенности
                    extracted_text += text + " "
                    logger.info(f"🔍 Текст: '{text}' (уверенность: {confidence:.2f})")
                else:
                    logger.info(f"🔍 Текст отброшен из-за низкой уверенности: '{text}' (уверенность: {confidence:.2f})")
            
            final_text = extracted_text.strip()
            logger.info(f"✅ Текст извлечен из изображения: {final_text[:100]}...")
            return final_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения текста: {e}")
            return None
    
    def extract_transaction_hash(self, text: str) -> Optional[str]:
        """
        Извлекает хеш транзакции из текста
        
        Args:
            text: Текст для поиска хеша
            
        Returns:
            Найденный хеш транзакции или None
        """
        if not text:
            logger.warning("⚠️ Текст пустой для поиска хеша")
            return None
        
        # Очищаем текст от лишних символов
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        logger.info(f"🔍 Ищем хеш в очищенном тексте: {clean_text[:200]}...")
        
        # Паттерны для различных типов хешей транзакций
        hash_patterns = [
            # TRX (Tron) - 64 символа hex
            r'\b[A-Fa-f0-9]{64}\b',
            # ETH/BSC - 66 символов с 0x
            r'\b0x[A-Fa-f0-9]{64}\b',
            # BTC - 64 символа hex
            r'\b[A-Fa-f0-9]{64}\b',
            # Короткие хеши (32 символа)
            r'\b[A-Fa-f0-9]{32}\b'
        ]
        
        # Ищем по всем паттернам
        for i, pattern in enumerate(hash_patterns):
            matches = re.findall(pattern, clean_text)
            if matches:
                # Берем первый найденный хеш
                hash_found = matches[0]
                logger.info(f"✅ Найден хеш транзакции по паттерну {i+1}: {hash_found}")
                return hash_found
        
        logger.info("🔍 Хеш не найден по паттернам, ищем по ключевым словам")
        
        # Если не нашли по паттернам, ищем по ключевым словам
        keywords = ['TxID', 'Transaction ID', 'Хеш', 'ID транзакции', 'Hash', 'TxID']
        for keyword in keywords:
            if keyword.lower() in clean_text.lower():
                logger.info(f"🔍 Найдено ключевое слово: {keyword}")
                # Ищем текст после ключевого слова
                pattern = rf'{re.escape(keyword)}[:\s]*([A-Fa-f0-9x]+)'
                match = re.search(pattern, clean_text, re.IGNORECASE)
                if match:
                    hash_found = match.group(1)
                    logger.info(f"✅ Найден хеш по ключевому слову {keyword}: {hash_found}")
                    return hash_found
        
        logger.info("🔍 Хеш не найден по ключевым словам, ищем по частям")
        
        # Попробуем найти хеш по частям (если OCR разбил его)
        # Ищем последовательности hex символов длиной от 16 до 64
        hex_parts = re.findall(r'\b[A-Fa-f0-9]{16,}\b', clean_text)
        if hex_parts:
            logger.info(f"🔍 Найдены hex части: {hex_parts}")
            # Сортируем по длине (самые длинные первыми)
            hex_parts.sort(key=len, reverse=True)
            for part in hex_parts:
                if len(part) >= 32:  # Минимальная длина для хеша
                    logger.info(f"✅ Найден потенциальный хеш по частям: {part}")
                    return part
        
        logger.info("🔍 Хеш не найден по частям, ищем длинные последовательности")
        
        # Последняя попытка - ищем любые длинные последовательности hex
        long_hex = re.findall(r'\b[A-Fa-f0-9]{20,}\b', clean_text)
        if long_hex:
            longest_hex = max(long_hex, key=len)
            logger.info(f"✅ Найден длинный hex как потенциальный хеш: {longest_hex}")
            return longest_hex
        
        logger.warning("⚠️ Хеш транзакции не найден в тексте")
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
            
            # Ищем хеш транзакции
            tx_hash = self.extract_transaction_hash(text)
            if tx_hash:
                result['hash'] = tx_hash
                result['success'] = True
                logger.info(f"✅ Хеш найден: {tx_hash}")
            else:
                logger.warning("⚠️ Хеш не найден")
            
            # Ищем сумму (паттерн для USDT, USD, UAH)
            amount_pattern = r'(\d+(?:\.\d+)?)\s*(USDT|USD|UAH|₴|\$)'
            amount_match = re.search(amount_pattern, text, re.IGNORECASE)
            if amount_match:
                result['amount'] = f"{amount_match.group(1)} {amount_match.group(2)}"
                logger.info(f"✅ Сумма найдена: {result['amount']}")
            
            # Определяем сеть по ключевым словам
            if 'TRX' in text.upper() or 'TRC20' in text.upper():
                result['network'] = 'TRC20'
                logger.info("✅ Сеть определена: TRC20")
            elif 'ERC20' in text.upper() or 'ETH' in text.upper():
                result['network'] = 'ERC20'
                logger.info("✅ Сеть определена: ERC20")
            elif 'BSC' in text.upper() or 'BNB' in text.upper():
                result['network'] = 'BSC'
                logger.info("✅ Сеть определена: BSC")
            
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

# Создаем глобальный экземпляр парсера
transaction_parser = TransactionImageParser() 