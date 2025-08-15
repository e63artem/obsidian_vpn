#!/bin/bash

# Обновляем миграции Alembic
python -m alembic upgrade head

# Запускаем основное приложение
python main.py