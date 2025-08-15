import os
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

import db

start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='✅ ПОДКЛЮЧИТЬ VPN ✅', callback_data='connect_vpn')],
    [InlineKeyboardButton(text='👤 Профиль', callback_data='account')],
    [InlineKeyboardButton(text='💰 Приведи друга', callback_data='referral')],
    [InlineKeyboardButton(text='👥 Поддержка', callback_data='help')],
    [InlineKeyboardButton(text='🔗 Добавить устройства', callback_data='add_device')]
])


def connect_vpn(config_id: Optional[int] = None) -> InlineKeyboardMarkup:
    tariffs = [
        ('🚀    1 мес - 299₽', 'tariff_1'),
        ('🚀    3 мес - 699₽', 'tariff_3'),
        ('🚀    6 мес - 1199₽', 'tariff_6'),
        ('🚀    12 мес - 2299₽', 'tariff_12')
    ]

    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"{cb}_{config_id}_cid" if config_id else cb
        )]
        for label, cb in tariffs
    ]
    buttons.append([InlineKeyboardButton(text='Главное меню', callback_data='main_menu')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


nums = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='1'),
     KeyboardButton(text='2')],
    [KeyboardButton(text='3'),
     KeyboardButton(text='4')],
    [KeyboardButton(text='5')]
], resize_keyboard=True, one_time_keyboard=True)


async def account(
        uid: int
) -> Optional[InlineKeyboardMarkup]:
    user_devices = await db.get_user_devices(uid)
    keyboard = []

    if not user_devices:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
        ])
        return markup

    for device in user_devices:
        filename = str(device.filename)
        filename = os.path.basename(filename)
        name = f'{device.device}_{device.uid}_{filename}'
        btn = [InlineKeyboardButton(
            text=f'{name}',
            callback_data=f'device_{device.id}'
        )]
        keyboard.append(btn)
    keyboard.append(
        [InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return markup


def payment_options(months: int):
    data = f'yookassa_{months}'
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💳 Картой', callback_data=data)],
        [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
    ])
    return markup


use_credits = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='✅ Списать', callback_data='use')],
    [InlineKeyboardButton(text='❌ Не списывать', callback_data='not use')],
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])


ref_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Нет кода', callback_data='no_ref')],
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])


main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])

help_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='📚 Инструкции', callback_data='instructions')],
    [InlineKeyboardButton(text='🆘 Написать в поддержку', url='https://t.me/rare_admin')],
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])

add_device = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='IOS', callback_data='ios')],
    [InlineKeyboardButton(text='ANDROID', callback_data='android')],
    [InlineKeyboardButton(text='WINDOWS', callback_data='windows')],
    [InlineKeyboardButton(text='MACOS', callback_data='mac')],
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])

choose_device = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='IOS', callback_data='choose_ios')],
    [InlineKeyboardButton(text='ANDROID', callback_data='choose_android')],
    [InlineKeyboardButton(text='WINDOWS', callback_data='choose_windows')],
    [InlineKeyboardButton(text='MACOS', callback_data='choose_mac')],
    [InlineKeyboardButton(text='Главное меню', callback_data='main_menu')]
])
phone = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Отправить номер телефона', request_contact=True)]
], resize_keyboard=True, one_time_keyboard=True)


def get_instruction(device: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Инструкция', callback_data=f'{device}_instructions')],
    ])
    return markup


close_instruction = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Скрыть инструкцию', callback_data='close')]
])


def back_to_acc(device_id: int):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='♻️ Продлить подписку', callback_data=f'renew_{device_id}')],
        [InlineKeyboardButton(text='Назад', callback_data='account')]
    ])
    return markup