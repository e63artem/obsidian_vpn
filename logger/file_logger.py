import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from config import Config

# Настройка директории для логов
# logs_directory = "./logger"
# if not os.path.exists(logs_directory):
#     os.makedirs(logs_directory)

# Формат логов
log_format = "[%(asctime)s] %(levelname)s %(source)s: %(message)s"


class CustomLogger:
    """
    Класс для создания кастомного логгера с поддержкой вывода в файл, консоль или оба варианта.
    """

    def __init__(self, source: str,
                 log_to_file: bool = True,
                 log_to_console: bool = True,
                 base_dir: str = "./log",
                 log_rotate_days: int = Config.LOG_ROTATE_DAYS):
        """
        Инициализация логгера.

        :param source: Источник логов (например, "System" или "user_123").
        :param log_to_file: Включить запись логов в файл (по умолчанию True).
        :param log_to_console: Включить вывод логов в консоль (по умолчанию True).
        :param base_dir: Директория для хранения логов (по умолчанию "./log").
        :param log_rotate_days: Период ротации логов в днях (по умолчанию 1 день).
        """
        self.source = source
        self.logger = logging.getLogger(f"custom_logger_{source}")
        self.logger.setLevel(logging.INFO)  # Устанавливаем минимальный уровень логирования

        # Очистка старых обработчиков
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Создаем директорию для логов, если она не существует
        self.log_directory = base_dir
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)

        # Формат логов
        self.formatter = logging.Formatter(log_format)

        # Настройка обработчиков
        if log_to_file:
            self._setup_file_handler(log_rotate_days)
        self._setup_console_handlers(log_to_console)

    def destroy(self):
        """
        Закрытие всех обработчиков логгера.
        """
        for handler in self.logger.handlers[:]:
            try:
                handler.close()
                self.logger.removeHandler(handler)
            except Exception as e:
                print(f"Ошибка при закрытии обработчика: {e}")

    def _setup_file_handler(self, log_rotate_days: int):
        """
        Настройка обработчика для записи логов в файл.

        :param log_rotate_days: Период ротации логов в днях.
        """
        log_file_path = os.path.join(self.log_directory, f"{self.source}_{datetime.now().strftime('%Y_%m_%d')}.log")
        file_handler = TimedRotatingFileHandler(
            log_file_path,
            when="midnight",
            interval=log_rotate_days,
            backupCount=5,
            encoding='utf-8',
            delay=True  # Отложить открытие файла до первой записи
        )
        file_handler.setLevel(logging.DEBUG)  # Записываем все уровни логов в файл
        file_handler.setFormatter(self.formatter)

        # Переопределение имени файла при ротации
        def rename_rotated_logs(prefix):
            def namer(default_name):
                base_filename, ext = os.path.splitext(os.path.basename(default_name))
                rotated_time = base_filename.split(".")[1]
                new_filename = f"{prefix}_{rotated_time}{ext}"
                return os.path.join(self.log_directory, new_filename)
            return namer

        file_handler.namer = rename_rotated_logs(self.source)

        # Переопределение метода doRollover для закрытия файлов
        original_do_rollover = file_handler.doRollover

        def custom_do_rollover():
            original_do_rollover()  # Вызов оригинального метода
            for handler in self.logger.handlers[:]:
                if isinstance(handler, TimedRotatingFileHandler):
                    try:
                        handler.stream.close()  # Явно закрыть файл
                    except Exception as e:
                        c = 1
                        # logger.error(f"Ошибка при закрытии файла: {e}")

        file_handler.doRollover = custom_do_rollover

        self.logger.addHandler(file_handler)

    def _setup_console_handlers(self, log_to_console: bool):
        """
        Настройка обработчиков для вывода логов в консоль.

        :param log_to_console: Включить вывод логов в консоль.
        """
        # Обработчик для вывода ERROR и CRITICAL всегда
        error_console_handler = logging.StreamHandler()
        error_console_handler.setLevel(logging.ERROR)  # Только ERROR и выше
        error_console_handler.setFormatter(self.formatter)
        self.logger.addHandler(error_console_handler)

        # Обработчик для вывода остальных уровней только при log_to_console=True
        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # Все уровни логов
            console_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)

    def _log(self, level: int, message: str):
        """
        Внутренний метод для логирования сообщений.

        :param level: Уровень логирования (например, logging.INFO).
        :param message: Сообщение для логирования.
        """
        self.logger.log(level, message, extra={"source": self.source})

    def info(self, message: str):
        """Логирование информационных сообщений."""
        self._log(logging.INFO, message)

    def error(self, message: str):
        """Логирование сообщений об ошибках."""
        self._log(logging.ERROR, message)

    def warning(self, message: str):
        """Логирование предупреждений."""
        self._log(logging.WARNING, message)

    def debug(self, message: str):
        """Логирование отладочных сообщений."""
        self._log(logging.DEBUG, message)

    def critical(self, message: str):
        """Логирование критических ошибок."""
        self._log(logging.CRITICAL, message)