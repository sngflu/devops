FROM python:3.9-slim-buster

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка необходимых пакетов pip для увеличения надежности
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Копирование только requirements.txt для использования кэширования слоев Docker
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование остальных файлов проекта
COPY . .

EXPOSE 5174

CMD ["gunicorn", "--bind", "0.0.0.0:5174", "--timeout", "120", "wsgi:app"]

