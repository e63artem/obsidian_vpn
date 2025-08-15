#!/bin/bash

# 1. Обновление системы и установка необходимых пакетов
echo "Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Проверка наличия Python 3.12
echo "Проверка наличия Python 3.12..."
if command -v python3.12 &> /dev/null
then
    echo "Python 3.12 уже установлен."
else
    echo "Python 3.12 не обнаружен. Начинаем установку..."
    
    # Установка Python 3.12
    sudo apt install -y software-properties-common
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install -y python3.12 curl wget
    
    # Установка pip для Python 3.12
    wget https://bootstrap.pypa.io/get-pip.py
    sudo python3.12 get-pip.py
    
    # Установка venv
    sudo apt install -y python3.12-venv
fi

PROJECT_DIR="/srv/telegram-bot"

cd $PROJECT_DIR || exit

# Копирование .env.example в .env, если .env не существует
echo "Проверка наличия файла .env..."
if [ -f ".env" ]; then
    echo "Файл .env уже существует. Пропускаем копирование."
else
    if [ -f ".env.example" ]; then
        echo "Создание файла .env из .env.example..."
        cp .env.example .env
    else
        echo "Файл .env.example не найден. Пропускаем создание .env."
    fi
fi

# Создание виртуального окружения
echo "Создание виртуального окружения..."
python3.12 -m venv .venv

# Активация виртуального окружения
source .venv/bin/activate

# 4. Установка зависимостей из requirements.txt
echo "Установка зависимостей из requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# Инициализация Alembic (если используется)
if [ -f "alembic.ini" ]; then
    echo "Инициализация Alembic..."
    alembic upgrade head  # Применяем все миграции
else
    echo "Alembic не обнаружен. Пропускаем настройку миграций."
fi

# Создание директорий для логов и временных файлов
LOG_DIR="$PROJECT_DIR/logs"
TMP_DIR="$PROJECT_DIR/tmp_files"
MEDIA_DIR="$PROJECT_DIR/media"
DB_DIR="$PROJECT_DIR/db"
echo "Создание директорий для логов и временных файлов..."
sudo mkdir -p $LOG_DIR $TMP_DIR $MEDIA_DIR $DB_DIR
sudo chmod -R 755 $LOG_DIR $TMP_DIR $MEDIA_DIR $DB_DIR


# Настройка автозапуска бота через systemd
BOT_SERVICE_FILE="/etc/systemd/system/telegram_bot.service"
echo "Настройка автозапуска бота через systemd..."

cat <<EOF | sudo tee $BOT_SERVICE_FILE
[Unit]
Description=Telegram Bot

[Service]
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/bash -c 'source $PROJECT_DIR/.venv/bin/activate && python3.12 -m alembic upgrade head && python3.12 -m main'
Restart=on-failure
TimeoutStartSec=10
RestartSec=5
User=root
Group=root
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable telegram_bot.service
sudo systemctl restart telegram_bot.service

echo "Бот установлен и запущен!"

# Очистка системы от ненужных пакетов
echo "Очистка системы..."
sudo apt autoremove -y
sudo apt autoclean -y