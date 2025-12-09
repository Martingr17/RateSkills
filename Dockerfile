# Dockerfile в корне проекта
FROM python:3.11-slim

# Создаем рабочую директорию
WORKDIR /code

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY app/ /code/app/

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/code

# Запускаем
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
