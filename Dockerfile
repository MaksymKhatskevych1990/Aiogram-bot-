# Используем официальный образ Python
FROM python:3.12

ENV PYTHONUNBUFFERED=1

WORKDIR /app            # Рабочая директория внутри контейнера

COPY . .                

RUN pip install celery redis gevent aiohttp gspread oauth2client aiogram qrcode Pillow

# (Необязательно) Можно добавить CMD, чтобы контейнер не завершался сразу
CMD ["sleep", "infinity"]