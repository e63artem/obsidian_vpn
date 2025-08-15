import asyncio
import io
import os
import re

import gspread
from aiogram import Bot
from googleapiclient.http import MediaIoBaseDownload
from gspread import SpreadsheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

import db
from utils import logger
from config import Config, BASE_DIR


SHEET_ID = Config.SHEET_ID
FOLDER_ID = Config.FOLDER_ID
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_info = Config.GOOGLE_CREDENTIALS_JSON
creds = ServiceAccountCredentials.from_json_keyfile_name(Config.GOOGLE_CREDENTIALS_JSON, SCOPES)
client = gspread.authorize(creds)
bot = Bot(token=Config.BOT_TOKEN)

drive_service = build('drive', 'v3', credentials=creds)


async def send_info(info: list):
    try:
        logger.info('Called send_info')
        sheet = client.open_by_key(SHEET_ID).sheet1
        result = sheet.append_row(info)
        logger.info(f'Результат отправки данных в таблицу: {result}')
        return result
    except SpreadsheetNotFound:
        logger.error('Таблица не найдена')


async def get_instructions():
    logger.info('fetching info from google sheet')
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_values()
        rows = data[1:]  # Skip the header row
        logger.info('Data read successfully')
    except SpreadsheetNotFound:
        logger.error('Таблица не найдена. Проверьте корректность ID таблицы')
        return None

    msg_dict = {}
    for row in rows:
        header = row[0]
        txt = row[1]
        link = transform_google_drive_link(row[2]) if row[2] else None
        msg_dict[header] = [txt, link]
    return msg_dict


def download_file_from_drive(file_id: str, filename: str, dest_folder: str = "vpn_configs") -> str:
    os.makedirs(dest_folder, exist_ok=True)
    request = drive_service.files().get_media(fileId=file_id)

    file_path = os.path.join(dest_folder, filename)
    with io.FileIO(file_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    return file_path


def list_vpn_configs(folder_id: str = FOLDER_ID):
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return [f for f in files if f["name"].endswith(".conf")]


async def download_configs():
    config_list = list_vpn_configs()
    folder_path = os.path.join(BASE_DIR, "vpn_configs")
    os.makedirs(folder_path, exist_ok=True)
    existing_files = set(os.listdir(folder_path))  # Список уже загруженных файлов
    paths = []

    for config in config_list:
        if config['name'] in existing_files:
            logger.info(f'{config["name"]} уже существует, пропуск...')
            continue

        file_path = download_file_from_drive(config['id'], config['name'], folder_path)
        await asyncio.sleep(1.5)
        paths.append((file_path, config['id']))
    await db.update_configs(paths)


def transform_google_drive_link(link: str) -> str:
    """Преобразует обычную ссылку Google Диска в прямую ссылку для скачивания."""
    match = re.search(r"https://drive\.google\.com/file/d/([^/]+)/view", link)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return link
