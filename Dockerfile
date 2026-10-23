FROM python:3.12-slim

# Вывод без буферизации и в UTF-8 (корректная кириллица в консоли контейнера)
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала зависимости: слой кэшируется, пока requirements.txt не изменился
COPY requirements.txt .
RUN pip install -r requirements.txt

# Затем исходный код (лишнее исключено через .dockerignore)
COPY . .


CMD ["python", "main.py"]
