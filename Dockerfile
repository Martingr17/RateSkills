FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Создание пользователя
RUN useradd -m -u 1000 skilluser && chown -R skilluser:skilluser /app
USER skilluser

EXPOSE 5000

CMD ["python", "run.py"]