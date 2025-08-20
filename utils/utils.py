import asyncio
import os
from functools import wraps
from collections import defaultdict

from aiogram.fsm.context import FSMContext

from logger.file_logger import CustomLogger
from config import BASE_DIR


msg_ids = defaultdict(set)


user_country = {}
base_dir = os.path.join(BASE_DIR, 'logger', 'logs')
logger = CustomLogger('bot_log', base_dir=base_dir)
logger.info('logger initialized')

user_timers = {}
users = {}

captions: dict[str, str] = {
    'ios': '🍏 Ваша подписка продлена на {days} дней',
    'android': '🤖 Ваша подписка продлена на {days} дней',
    'windows': '💠 Ваша подписка продлена на {days} дней',
    'mac': '💻 Ваша подписка продлена на {days} дней',
}


def auto_state_clear(timeout=900):
    def decorator(func):
        @wraps(func)
        async def wrapper(message, state: FSMContext, *args, **kwargs):
            user_id = message.from_user.id

            if user_id in user_timers:
                task = user_timers[user_id]
                if not task.done():
                    task.cancel()

            async def timer():
                try:
                    await asyncio.sleep(timeout)
                    await state.clear()
                    users.pop(user_id, None)
                    user_timers.pop(user_id, None)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    # Можно подключить логгер
                    print(f"Ошибка в таймере для {user_id}: {e}")

            user_timers[user_id] = asyncio.create_task(timer())

            return await func(message, state, *args, **kwargs)

        return wrapper
    return decorator