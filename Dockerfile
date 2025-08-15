# Используем официальный образ Python в качестве базового
FROM python:3.12.3-slim as build-env

# Аргументы для сборки
ARG ENVIRONMENT

# Переменные окружения
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей в контейнер
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы приложения в контейнер
COPY . .

# Добавляем путь к пакету в PYTHONPATH (необязательно)
ENV PYTHONPATH=/app

# Делаем entrypoint.sh исполняемым и устанавливаем его как точку входа
#RUN chmod +x /app/entrypoint.sh
#ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]