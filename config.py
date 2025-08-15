import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Загрузка переменных окружения
if os.path.exists(os.path.join(BASE_DIR, '.env.local')):
    load_dotenv(os.path.join(BASE_DIR, '.env.local'))
else:
    load_dotenv(os.path.join(BASE_DIR, '.env'))

    
class Config:
    SHEET_ID = os.getenv('SHEET_ID')
    GOOGLE_CREDENTIALS_JSON = os.path.join(BASE_DIR, os.getenv('GOOGLE_CREDENTIALS_JSON'))
    DB_URL = f"sqlite+aiosqlite:///{BASE_DIR}/db/database/{os.getenv('DB_NAME')}"
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    LOG_ROTATE_DAYS = 1
    FOLDER_ID = os.getenv('FOLDER_ID')
    PROVIDER_TOKEN = os.getenv('PROVIDER_TOKEN')
    CHANNEL_ID = os.getenv('CHANNEL_ID')