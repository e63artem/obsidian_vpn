import asyncio
import json
import os.path
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, LabeledPrice, PreCheckoutQuery, \
    InputMediaDocument
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

import config
from config import Config
from bot import keyboards as kb
from utils import auto_state_clear, msg_ids, logger, captions
import db
from integrations import google_api as ggl

scheduler = AsyncIOScheduler()
dp = Dispatcher()
bot = Bot(token=Config.BOT_TOKEN)
user = {}


class States(StatesGroup):
    ref = State()
    phone_number = State()
    email = State()


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


async def delete_message_after(message: Message):
    await asyncio.sleep(120)
    try:
        await message.delete()
    except TelegramBadRequest as e:
        logger.error(f'Ошибка при удалении сообщений: {e}')


@dp.message(CommandStart(deep_link=True))
async def start_with_deeplink(message: Message, command: CommandObject):
    uid = message.from_user.id
    try:
        await db.delete_invoice(uid)
    except Exception:
        pass
    username = message.from_user.username if message.from_user.username else message.from_user.full_name
    ref_id = None
    if command.args:
        ref_id = command.args
        await db.update_user(uid, is_referrer=True)
    if int(ref_id) == uid:
        await message.answer('<b>Мне кажется, это плохая идея - '
                             'посылать реферальную ссылку самому себе!</b>',
                             parse_mode='HTML')
        ref_id = None
    try:
        msg = await bot.send_message(ref_id, 'Вашей реферальной ссылкой воспользовались! '
                                             'Теперь вы будете получать 25% от покупок вашего друга, а он - '
                                             '25% кешбека от своих покупок☺️')
        _ = asyncio.create_task(delete_message_after(msg))
    except TelegramBadRequest:
        pass
    success = await db.create_user(uid,
                                   username,
                                   ref_id=ref_id)
    if success:
        await message.answer_photo(FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
                                   reply_markup=kb.start_keyboard)
    else:
        await message.answer('Вы ранее уже активировали реферальную ссылку')
        await message.answer_photo(FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
                                   reply_markup=kb.start_keyboard)


@dp.message(CommandStart(deep_link=False))
async def start(message: Message):
    uid = message.from_user.id
    try:
        await db.delete_invoice(uid)
    except Exception as e:
        logger.info(f'{e}')
    username = message.from_user.username if message.from_user.username else message.from_user.full_name
    await db.create_user(uid,
                         username)
    await message.answer_photo(FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
                               reply_markup=kb.start_keyboard)


async def check_configs(callback: CallbackQuery) -> bool:
    configs = await db.get_all_configs()
    if not configs or all(conf["assigned"] for conf in configs):
        await callback.answer('⚠️ Ошибка ⚠️')
        await callback.message.answer(
            '⚠️ Сейчас нет доступных конфигураций, попробуйте ещё раз через 10 минут',
            reply_markup=kb.clear
        )
        await bot.send_message(
            Config.ADMIN_ID,
            'У вас закончились конфигурации, необходимо добавить ещё'
        )
        return False
    return True


@dp.callback_query()
@auto_state_clear()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    data = callback.data
    message = callback.message
    if data == 'main_menu':
        await state.clear()
        try:
            await db.delete_invoice(uid)
        except Exception as e:
            logger.info(f'{e}')
        try:
            await bot.delete_messages(uid, list(msg_ids[uid]))
            await message.delete()
        except TelegramBadRequest:
            logger.error(f"Ошибка при удалении сообщений для пользователя {uid}")
        await callback.answer('Главное меню')
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')))
        try:
            await message.edit_media(media, reply_markup=kb.start_keyboard)
        except TelegramBadRequest:
            await message.answer_photo(FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
                                       reply_markup=kb.start_keyboard)
    # ---------------------------Подключение ВПН-----------------------------
    elif data.startswith('choose_'):
        await db.reg_invoice(uid)
        device = data.split('_')[1]
        logger.info(f'Пользователь выбрал {device}')
        await callback.answer("Количество устройств")
        if db_user := await db.get_user_data(uid):
            logger.info('Пользователь найден')
            if phone_num := db_user.get('phone_number'):
                logger.info(f'Номер телефона найден: {phone_num}')
                if email := db_user.get('email'):
                    logger.info(f'Email найден: {email}')
                    user[uid] = {
                        'phone': phone_num,
                        'email': email,
                        'device': device
                    }
                    msg = await message.answer('Нужное Вам количество устройств:',
                                               #'количество устройств, которое вы хотите подключить',
                                               reply_markup=kb.nums)
                    msg_ids[uid].add(msg.message_id)
                    return
        logger.info('Пользователь не найден')
        if uid not in user:
            user[uid] = {}
        user[uid] = {
            'device': device
        }
        try:
            msg = await message.edit_caption(
                caption='Перед тем, как перейти к оплате, '
                        'вам необходимо зарегистрироваться. '
                        'Для начала, введите номер телефона по форме +79990000000:',
                reply_markup=kb.main_menu
            )
            msg_ids[uid].add(msg.message_id)
        except TelegramBadRequest:
            msg = await message.edit_text(
                'Перед тем, как перейти к оплате, вам необходимо зарегистрироваться. '
                'Для начала, введите номер телефона по форме +79990000000:',
                reply_markup=kb.main_menu
            )
            msg_ids[uid].add(msg.message_id)
        await state.set_state(States.phone_number)
        msg_ids[uid].add(message.message_id)
        logger.info(f'{user[uid]}')
    elif data == 'connect_vpn':
        if not await check_configs(callback):
            return
        await callback.answer("Выберите устройство")
        media = InputMediaPhoto(
            media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
            caption='Ваше устройство ⤵️'
        )
        msg = await message.edit_media(media, reply_markup=kb.choose_device)
        msg_ids[uid].add(msg.message_id)
    elif data.startswith('tariff_'):
        await callback.answer("Оплата")
        months = int(data.split('_')[1])
        user_info = await db.get_user_data(uid)
        user_credits = user_info['credits_on_account']
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
                                caption=f'Списать бонусные баллы?\n'
                                        f'🏦 Баланс: ({user_credits})\n'
                                        f'Минимальная сумма оплаты бонусами - 100₽')
        config_id = None
        if data.endswith('cid'):
            config_id = int(data.split('_')[2])
            conf_info = await db.get_config_by_id(config_id)
            await db.reg_invoice(uid)
            device = conf_info['device']
            user[uid] = {
                'device': device
            }
        match months:
            case 1:
                summ = 299
            case 3:
                summ = 699
            case 6:
                summ = 1199
            case 12:
                summ = 2299
            case _:
                summ = 299
        logger.info('updating invoice')
        invoice = await db.update_invoice(
            uid,
            summary=summ,
            days_to_increase=months*30,
            config_id=config_id
        )
        logger.info(f'{invoice}')
        await message.edit_media(media, reply_markup=kb.use_credits)
    elif data in ['use', 'not use']:
        flag = True if data == 'use' else False
        invoice = await db.update_invoice(
            uid,
            use_credits=flag,
        )
        months = int(invoice['days_to_increase']//30)
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')))
        await message.edit_media(media, reply_markup=kb.payment_options(months))
    elif data == 'no_ref':
        await state.clear()
        await message.edit_text('Инструкция к подключению',
                                reply_markup=kb.main_menu)
    # ---------------------------Личный кабинет------------------------------
    elif data == 'account':
        await callback.answer("Личный кабинет")
        me = await db.get_user_data(uid)
        pay_datetime = me['pay_date_time'] if me['pay_date_time'] else 'Не оплачено'
        credits_on_acc = me['credits_on_account']
        text = (f'📅 Дата последней оплаты:   {pay_datetime}\n\n'
                f'🏦 Бонусов на счету:   {credits_on_acc}\n\n'
                f'📱 Ваши устройства:')

        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')), caption=text)
        await message.edit_media(media, reply_markup=await kb.account(uid))
    # -------------------------Реферальная программа-------------------------
    elif data == 'referral':
        await callback.answer('Реферальная программа')
        msg_ids[uid].add(message.message_id)
        bot_info = await bot.me()
        ref_code = f'https://t.me/{bot_info.username}?start={uid}'
        await message.answer('🔥 Вам - 20% от каждого пополнения\n'
                             #'каждого, кто перейдет по вашей ссылке\n'
                             '🎁 Рефералу - скидка 20% на все тарифы\n'
                             '📍Количество рефералов не ограничено\n\n'
                             'Просто отправьте эту ссылку:\n\n'
                             f'<code>{ref_code}</code>',
                             reply_markup=kb.main_menu,
                             parse_mode='HTML')
    # --------------------------------Помощь---------------------------------
    elif data == 'help':
        await callback.answer('Помощь')
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')))
        await message.edit_media(media, reply_markup=kb.help_kb)
    elif data == 'instructions':
        instructions = await ggl.get_instructions()
        headers: list[str] = list(instructions.keys())
        texts: list[str] = []
        links = []
        if instructions:
            for header in headers:
                _text, _link = instructions[header]
                text: str = _text
                link: str = _link
                texts.append(text)
                links.append(link)
            await message.delete()
            for i in range(len(headers)):
                try:
                    reply_markup = kb.main_menu if i + 1 == len(headers) else None
                    if links[i]:
                        msg = await bot.send_photo(
                            chat_id=uid,
                            photo=links[i],
                            caption=f'<b>{headers[i].capitalize()}</b>\n\n{texts[i]}',
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
                    else:
                        msg = await bot.send_message(
                            chat_id=uid,
                            text=f'<b>{headers[i].capitalize()}</b>\n\n{texts[i]}',
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
                    msg_ids[uid].add(msg.message_id)
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления {headers[i]} для {uid}: {e}")
        else:
            await message.edit_caption(caption='К сожалению, инструкции сейчас недоступны...',
                                       reply_markup=kb.main_menu)
    # ---------------------------- Оплата --------------------------------s
    elif data.startswith('yookassa_'):
        await message.delete()
        months = int(data.split('_')[1])
        days = months * 30
        match months:
            case 1:
                summ = 299
            case 3:
                summ = 699
            case 6:
                summ = 1199
            case 12:
                summ = 2299
            case _:
                summ = 299
        invoice_info = await db.get_invoice_by_uid(uid)
        number_of_configs = int(invoice_info['number_of_configs'])
        logger.info(number_of_configs)
        summ *= number_of_configs
        logger.info(summ)
        use_credits = invoice_info['use_credits']
        if db_user := await db.get_user_data(uid):
            logger.info('Пользователь найден')
            if phone_num := db_user.get('phone_number'):
                logger.info(f'Номер телефона найден: {phone_num}')
                if email := db_user.get('email'):
                    logger.info(f'Email найден: {email}')
                    user[uid]['phone'] = phone_num
                    user[uid]['email'] = email
        credits_on_acc = db_user['credits_on_account']
        if use_credits and credits_on_acc > 0:
            if summ <= credits_on_acc:
                credits_used = summ - 100
                summ = 100
                credits_on_acc -= credits_used
            elif credits_on_acc <= summ - 100:
                summ -= credits_on_acc
                credits_on_acc = 0
            else:
                credits_used = summ - 100
                summ = 100
                credits_on_acc -= credits_used
        name, price = 'Оплата VPN', summ * 100
        pr = [LabeledPrice(label=name, amount=int(price))]
        description = f'{days} дней подписки - {summ} рублей'
        time_data = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
        pld = f'{callback.from_user.id}_{time_data}_{credits_on_acc}'
        provider_data = {
            'receipt': {
                'customer': {
                    'full_name': callback.from_user.full_name,
                    'phone': user[uid]['phone'],
                    'email': user[uid]['email']
                },
                'items': [
                    {
                        'description': description,
                        'quantity': 1,
                        'amount': {
                            'value': price / 100,
                            'currency': 'RUB'
                        },
                        "vat_code": 1,
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity"
                    }
                ],
                "tax_system_code": 1
            }
        }
        invoice = None
        try:
            invoice = await \
                callback.message.answer_invoice(title=name,
                                                description=description,
                                                payload=pld,
                                                provider_token=Config.PROVIDER_TOKEN,
                                                currency='RUB',
                                                prices=pr,
                                                provider_data=json.dumps(provider_data),
                                                )
        except Exception as e:
            logger.error(f"{e}")
        msg_ids[uid].add(invoice.message_id)
        back_msg = await message.answer('Вернуться в главное меню ⤵️',
                                        reply_markup=kb.main_menu)
        msg_ids[uid].add(back_msg.message_id)
    elif data == 'add_device':
        if not await check_configs(callback):
            return
        media = InputMediaPhoto(
            media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')),
            caption='Ваше устройство ⤵️'
        )
        msg = await message.edit_media(media, reply_markup=kb.choose_device)
        msg_ids[uid].add(msg.message_id)
    elif data in ['ios', 'android', 'windows', 'mac']:
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')))
        await message.edit_media(media, reply_markup=kb.connect_vpn())
    elif data.startswith('device_'):
        config_id = data.split('_')[1]
        config_info = await db.get_config_by_id(config_id)
        conf_path = config_info['filename']
        device: str = config_info['device']
        exp_date = config_info['expired']  # строка вида 'YYYY-MM-DD'
        now = datetime.now().strftime('%Y-%m-%d')

        # Преобразуем строки в объекты datetime
        exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
        now_dt = datetime.strptime(now, '%Y-%m-%d')

        # Вычисляем разницу в днях
        days_left = (exp_dt - now_dt).days
        await message.delete()

        try:
            # Отправляем файл с конфигурацией
            await callback.message.answer_document(
                document=FSInputFile(conf_path),
                caption=f"📲 Тип устройства - {device}\n"
                        f"⏳ Истекает через {days_left} дней",
                reply_markup=kb.back_to_acc(int(config_id))
            )
            await callback.answer("Конфигурация отправлена")

            # Логирование успешной отправки
            logger.info(f"Пользователю {uid} отправлен конфиг {config_id}")

        except FileNotFoundError:
            logger.error(f"Файл конфигурации не найден: {conf_path}")
            await callback.answer("Ошибка: файл конфигурации не найден", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка при отправке конфига {config_id} пользователю {uid}: {str(e)}")
            await callback.answer(f"Ошибка при отправке: {str(e)}", show_alert=True)
    elif data.startswith('renew_'):
        config_id = data.split('_')[1]
        await callback.answer("Продлить подписку")
        media = InputMediaPhoto(media=FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png')))
        await message.edit_media(media, reply_markup=kb.connect_vpn(int(config_id)))
    elif data.endswith('_instructions'):
        await callback.answer('Инструкция к подключению')
        device = data.split('_')[0]
        instructions = await ggl.get_instructions()
        headers: list[str] = list(instructions.keys())
        texts: list[str] = []
        links = []
        if instructions:
            for header in headers:
                _text, _link = instructions[header]
                text: str = _text
                link: str = _link
                texts.append(text)
                links.append(link)
            for i in range(len(headers)):
                if headers[i] == device:
                    logger.info(f'Header: {headers[i]}, device: {device}')
                    if links[i] is not None:
                        await bot.send_photo(
                            chat_id=uid,
                            photo=links[i],
                            caption=f'<b>{headers[i].capitalize()}</b>\n\n{texts[i]}',
                            reply_markup=kb.close_instruction,
                            parse_mode='HTML'
                        )
                    else:
                        await bot.send_message(
                            chat_id=uid,
                            text=f'<b>{headers[i].capitalize()}</b>\n\n{texts[i]}',
                            reply_markup=kb.close_instruction,
                            parse_mode='HTML'
                            )
        else:
            await message.edit_caption(caption='К сожалению, инструкция сейчас недоступна...',
                                       reply_markup=kb.main_menu)
    elif data == 'close':
        await message.delete()
    await callback.answer()


@dp.message(F.text.isdigit())
async def numbers_handler(message: Message):
    uid = message.from_user.id
    msg_ids[uid].add(message.message_id)
    number = int(message.text)
    logger.info(number)
    if number > 100 or number < 1:
        msg = await message.answer("❌ Некорректное количество. Попробуйте ещё раз.", reply_markup=kb.nums)
        msg_ids[uid].add(msg.message_id)
        return
    invoice = await db.update_invoice(
        uid,
        number_of_configs=number
    )
    media = FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png'))
    await message.answer_photo(media, reply_markup=kb.connect_vpn())


@dp.message(States.ref)
@auto_state_clear()
async def ref_handler(message: Message, state: FSMContext):
    await state.update_data(ref_code=message.text)
    await message.answer('Инструкция к подключению',
                         reply_markup=kb.main_menu)


@dp.message(States.phone_number)
@auto_state_clear()
async def phone_number_handler(message: Message, state: FSMContext):
    uid = message.from_user.id
    msg_ids[uid].add(message.message_id)
    phone_num = message.text
    phone_pattern = re.compile(r"^\+7\d{10}$")
    if not phone_pattern.match(phone_num):
        msg = await message.answer("❌ Некорректный номер телефона. Попробуйте ещё раз.")
        msg_ids[uid].add(msg.message_id)
        return
    user[uid]['phone'] = phone_num
    msg = await message.answer('Теперь введите ваш email:')
    msg_ids[uid].add(msg.message_id)
    await state.set_state(States.email)


@dp.message(States.email)
async def email_handler(message: Message, state: FSMContext):
    uid = message.from_user.id
    msg_ids[uid].add(message.message_id)
    email = message.text
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not email_pattern.match(email):
        msg = await message.answer("❌ Некорректный email. Попробуйте ещё раз.")
        msg_ids[uid].add(msg.message_id)
        return
    await state.clear()
    user[uid]['email'] = email
    kw = {
        'phone_number': user[uid]['phone'],
        'email': email
    }
    await db.update_user(uid, **kw)
    # photo = FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png'))
    msg = await message.answer(
        'Введите (только числом) или выберите на клавиатуре '
        'количество конфигураций, которое вы хотите приобрести',
        reply_markup=kb.nums
    )
    msg_ids[uid].add(msg.message_id)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    uid = message.from_user.id
    payment_info = message.successful_payment
    try:  # Удаление лишних сообщений
        for msg_id in msg_ids[uid]:
            await bot.delete_message(message.chat.id, msg_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщений: {e}")
    await message.answer(f"✅ Ваш платеж на сумму\n"
                         f"{payment_info.total_amount / 100} {payment_info.currency} "
                         f"был успешно обработан\n"
                         f"🤝 Спасибо, что Вы с нами!")
    pld = payment_info.invoice_payload
    credits_on_acc = int(pld.split('_')[2])
    await db.update_user(
        uid,
        credits_on_account=credits_on_acc
    )
    summ = payment_info.total_amount / 100
    invoice_data = await db.get_invoice_by_uid(uid)
    number_of_configs = invoice_data['number_of_configs']
    days = invoice_data['days_to_increase']
    info = await db.get_user_data(uid)
    ref_id = info['referrer']
    my_credits = info['credits_on_account']
    if ref_id is not None and ref_id != 'None':
        ref_info = await db.get_user_data(ref_id)
        ref_credits = ref_info['credits_on_account']
        await db.update_user(
            ref_id,
            credits_on_account=ref_credits + int(summ * 0.25),
        )
        await db.update_user(
            uid,
            credits_on_account=my_credits + int(summ * 0.25),
            referrer='None'
        )
    days_left = int(info['subscribe_days_left'])
    days_for_db = days + days_left
    now = datetime.now().strftime(format='%Y-%m-%d')
    await db.update_user(uid, pay_date_time=now, subscribe_days_left=days_for_db)
    invoice = await db.update_invoice(uid, paid=True, paid_at=now)
    await db.delete_invoice(uid)
    exp_date = (datetime.now() + timedelta(days=days)).strftime(format='%Y-%m-%d')
    config_id = invoice['config_id']
    if not config_id:
        media_group = []
        for i in range(number_of_configs):
            user_config = await db.get_free_vpn_config(uid, exp_date, user[uid]['device'])
            logger.info(f'{user_config}')
            file = FSInputFile(path=user_config['filename'])
            device = user_config['device']
            media = InputMediaDocument(
                media=file,
                caption=captions[device].format(days=days),
            )
            media_group.append(media)
        await message.answer_media_group(media_group)
        await message.answer('Чтобы получить инструцкию, нажмите кнопку ниже:',
                             reply_markup=kb.get_instruction(user[uid]['device']))
    else:
        conf_info = await db.get_config_by_id(config_id)
        expired_date = datetime.strptime(conf_info['expired'], '%Y-%m-%d')
        new_expired_date = expired_date + timedelta(days=days)
        exp_date_str = new_expired_date.strftime('%Y-%m-%d')
        await db.update_exp_date(config_id, exp_date_str)
        device = conf_info['device']
        await message.answer(f'🔄 Ваша подписка для {device} продлена на {days} дней.')
    photo = FSInputFile(path=os.path.join(config.BASE_DIR, 'static/img.png'))
    await message.answer_photo(photo, reply_markup=kb.start_keyboard)


async def check_subscriptions():
    configs = await db.get_all_users()
    for conf in configs:
        device_id = conf['id']
        uid = conf['uid']
        device_type = conf['device']
        filename = str(conf['filename'])
        filename = os.path.basename(filename)
        expired_date = datetime.strptime(conf['expired'], "%Y-%m-%d").date()
        is_active = expired_date < datetime.now().date()
        if is_active:
            user_info = await db.get_user_data(uid)
            days_left = user_info['subscribe_days_left']
            phone = user_info['phone']
            conf_id = conf['file_id']
            if days_left == 0:
                try:
                    await bot.send_message(
                        Config.CHANNEL_ID,
                        f'У пользователя c id {uid} и '
                        f'номером телефона: {phone} \n'
                        'срок действия подписки закончился, оплата не внесена\n\n'
                        'Ссылка на конфигурацию для отключения: \n'
                        f'https://drive.google.com/file/d/{conf_id}/view?usp=drive_link'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
                await asyncio.sleep(1)
                try:
                    await bot.send_message(uid, 'Здравствуйте!\n\n'
                                                'Срок действия вашей подписки для конфигурации '
                                                f'{device_type}_{uid}_{filename} истёк, рекомендуем её продлить.',
                                           reply_markup=kb.back_to_acc(device_id))
                    await last_notification(uid, device_id)
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
            elif days_left < 3:
                try:
                    await bot.send_message(
                        Config.CHANNEL_ID,
                        f'У пользователя с id {uid} '
                        'срок действия подписки меньше 3-х дней, оплата не внесена'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
                await asyncio.sleep(1)
                try:
                    await bot.send_message(uid, f'Здравствуйте!\n\n'
                                                'Срок действия вашей подписки для конфигурации '
                                                f'{device_type}_{uid}_{filename} меньше 3-х дней, '
                                                'рекомендуем её продлить.',
                                           reply_markup=kb.back_to_acc(device_id))
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
            await asyncio.sleep(1)


async def last_notification(uid, device_id):
    user_ = await bot.get_chat(uid)
    name = user_.full_name
    text = f'''Здравствуйте, {name}!

Срок действия вашей подписки закончился, для возобновления пользованием VPN, рекомендуем её подключить'''
    scheduler.add_job(bot.send_message, DateTrigger(datetime.now() + timedelta(days=3)),
                      args=[uid, text],
                      kwargs={'reply_markup': kb.back_to_acc(device_id)})


async def main():
    await db.init_db()
    # ------------------------- Расписание задач -------------------------
    scheduler.remove_all_jobs()  # сначала очищаем (если нужно)
    scheduler.add_job(ggl.download_configs, trigger=IntervalTrigger(minutes=10))
    scheduler.add_job(db.decrease_all_subscriptions, trigger=CronTrigger(hour=11, minute=40))
    scheduler.add_job(check_subscriptions, trigger=CronTrigger(hour=12))
    scheduler.start()  # затем запускаем планировщик
    #  -------------------------------------------------------------------
    _ = asyncio.create_task(ggl.download_configs())
    await dp.start_polling(bot)
