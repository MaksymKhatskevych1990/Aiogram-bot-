# 🪟 Настройка и запуск на Windows

## 🚨 Решение проблем с Celery на Windows

Проблемы с `PermissionError` и `OSError` в Celery на Windows решены путем настройки:
- `worker_pool="solo"` - используем solo pool вместо multiprocessing
- `worker_concurrency=1` - один воркер для стабильности
- `task_acks_late=True` - подтверждаем задачи после выполнения

## 🚀 Способы запуска

### 1. Автоматические скрипты (рекомендуется)

#### Batch файлы (.bat):
```cmd
# Запуск воркера
start_worker.bat

# Запуск планировщика
start_beat.bat

# Запуск бота
start_bot.bat

# Инструкции по запуску всех компонентов
start_all.bat
```

#### PowerShell скрипты (.ps1):
```powershell
# Запуск воркера
.\start_worker.ps1

# Запуск планировщика
.\start_beat.ps1

# Запуск бота
.\start_bot.ps1
```

### 2. Ручной запуск

#### Терминал 1 - Воркер:
```cmd
venv\Scripts\activate
celery -A celery_app worker --loglevel=info --pool=solo --concurrency=1
```

#### Терминал 2 - Beat:
```cmd
venv\Scripts\activate
celery -A celery_app beat --loglevel=info
```

#### Терминал 3 - Бот:
```cmd
venv\Scripts\activate
python main.py
```

## 📋 Порядок запуска

1. **Сначала**: Убедитесь, что Redis запущен
2. **Затем**: Запустите Celery Worker (Терминал 1)
3. **Потом**: Запустите Celery Beat (Терминал 2)
4. **Наконец**: Запустите основного бота (Терминал 3)

## 🔧 Проверка работы

### Проверка воркера:
```cmd
celery -A celery_app inspect active
```

### Проверка зарегистрированных задач:
```cmd
celery -A celery_app inspect registered
```

### Проверка статистики:
```cmd
celery -A celery_app inspect stats
```

## 🛠️ Troubleshooting

### Если воркер не запускается:
1. Убедитесь, что Redis работает: `redis-cli ping`
2. Проверьте переменные окружения в `.env`
3. Запустите с отладкой: `celery -A celery_app worker --loglevel=debug`

### Если возникают ошибки импорта:
1. Убедитесь, что виртуальное окружение активировано
2. Проверьте, что все зависимости установлены: `pip install -r requirements.txt`

### Если задачи не выполняются:
1. Проверьте, что beat запущен
2. Убедитесь, что воркер подключен к Redis
3. Проверьте логи воркера на наличие ошибок

## 📊 Мониторинг (опционально)

### Установка Flower для веб-мониторинга:
```cmd
pip install flower
celery -A celery_app flower
```

Затем откройте http://localhost:5555 в браузере.

## ⚠️ Важные замечания

1. **Не запускайте все компоненты в одном терминале** - используйте отдельные окна
2. **Порядок запуска важен** - сначала воркер, потом beat, потом бот
3. **Redis должен быть запущен** перед всеми компонентами
4. **Используйте solo pool** для стабильной работы на Windows

## 🎯 Быстрый старт

1. Запустите Redis
2. Дважды кликните на `start_worker.bat`
3. Дважды кликните на `start_beat.bat`
4. Дважды кликните на `start_bot.bat`

Готово! 🎉
