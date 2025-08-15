from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError

from db.models import async_session, User, VpnConfig, TmpInvoice
from utils import logger


async def create_user(
        uid: int,
        username: str,
        pay_date_time: str | None = None,
        subscribe_days_left: int = 0,
        ref_id: int | None = None,
        is_trial: bool = True,
        is_active: bool = False,
):
    async with async_session() as session:
        current_user = await session.get(User, uid)
        if current_user:
            if ref_id and current_user.referrer is None:
                current_user.referrer = ref_id
                await session.commit()
                return current_user
            elif current_user.referrer is not None:
                return
            return

        user = User(
            uid=uid,
            username=username,
            pay_date_time=pay_date_time,
            subscribe_days_left=subscribe_days_left,
            referrer=ref_id,
            is_trial=is_trial,
            is_active=is_active,
            credits_on_account=0,
        )
        session.add(user)
        await session.commit()
        return user


async def update_user(
        uid: int,
        **kwargs
) -> Optional[dict]:
    allowed_fields = {
        "username",
        "phone_number",
        "email",
        "pay_date_time",
        "subscribe_days_left",
        "referrer",
        "is_referrer",
        "is_trial",
        "is_active",
        "credits_on_account",
    }

    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            return None

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(user, key, value)

        await session.commit()
        return user.as_dict()


async def decrease_all_subscriptions():
    async with async_session() as session:
        try:
            stmt = (
                update(User)
                .where(User.subscribe_days_left > 0)
                .values(subscribe_days_left=User.subscribe_days_left - 1)
            )
            await session.execute(stmt)
            await session.commit()
            logger.info(f"[{datetime.now()}] Уменьшены дни подписки у пользователей")
        except Exception as e:
            await session.rollback()
            logger.error(f"[{datetime.now()}] Ошибка при обновлении дней подписки: {e}")


async def update_configs(paths: list[tuple[str, str]]):
    async with async_session() as session:
        try:
            for file_path, file_id in paths:
                filename = file_path  # Имя файла из пути
                result = await session.execute(
                    select(VpnConfig).where(VpnConfig.file_id == file_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    logger.info(f"Файл {filename} (ID: {file_id}) уже существует в БД, пропуск...")
                    continue
                new_config = VpnConfig(
                    file_id=file_id,
                    filename=filename,
                    assigned=False,
                    uid=None
                )
                session.add(new_config)
                logger.info(f"Добавлен конфиг {filename} в БД")
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка при обновлении конфигов в БД: {e}")


async def get_user_data(uid):
    async with async_session() as session:
        me = await session.get(User, uid)
        return me.as_dict()


async def get_all_users() -> list[dict]:
    async with async_session() as session:
        users = await session.execute(select(User))
        return [user.as_dict() for user in users.scalars()]


async def get_all_configs() -> list[dict]:
    async with async_session() as session:
        configs = await session.execute(select(VpnConfig))
        return [conf.as_dict() for conf in configs.scalars()]


async def get_config_by_id(config_id):
    async with async_session() as session:
        config = await session.get(VpnConfig, config_id)
        return config.as_dict() if config else None


async def get_free_vpn_config(
        uid: int,
        exp_date: str,
        device: str,
) -> dict | None:
    # Получаем первый свободный конфиг
    async with async_session() as session:
        result = await session.execute(
            select(VpnConfig).where(VpnConfig.assigned.is_(False)).limit(1)
        )
        config = result.scalar_one_or_none()

        if config:
            # Помечаем как выданный
            await session.execute(
                update(VpnConfig)
                .where(VpnConfig.id == config.id)
                .values(
                    assigned=True,
                    uid=uid,
                    expired=exp_date,
                    device=device
                )
            )
            await session.commit()
            return config.as_dict()
        return None


async def update_exp_date(
        config_id: int,
        new_date: str,
) -> dict | None:
    async with async_session() as session:
        config = await session.get(VpnConfig, config_id)
        logger.info(f'{config.as_dict()}')
        if config:
            config.expired = new_date
            await session.commit()
            return config.as_dict()
        return None


async def get_user_devices(uid) -> list[VpnConfig]:
    async with async_session() as session:
        user_devices = await session.execute(
            select(VpnConfig).where(VpnConfig.uid == uid)
        )
        return user_devices.scalars().all()


async def reg_invoice(
        uid: int,
        summary: int = None,
        days_to_increase: int = None,
        config_id: Optional[int] = None,
        number_of_configs: int = 1,
) -> dict | None:
    async with async_session() as session:
        try:
            # Проверяем существование конфига, если передан config_id
            if config_id is not None:
                config = await session.get(VpnConfig, config_id)
                if not config:
                    return None

            # Создаем новую временную инвойс-запись
            new_invoice = TmpInvoice(
                uid=uid,
                config_id=config_id,
                summary=summary,
                days_to_increase=days_to_increase,
                number_of_configs=number_of_configs,
                paid=False,
                paid_at=None,
                created_at=datetime.now().strftime('%Y-%m-%d')
            )

            # Добавляем в сессию и коммитим
            session.add(new_invoice)
            await session.commit()
            await session.refresh(new_invoice)

            # Возвращаем данные инвойса в виде словаря
            return new_invoice.as_dict()

        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка при создании временного инвойса: {str(e)}")
            return None


async def get_invoice_by_uid(uid: int) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(TmpInvoice).where(TmpInvoice.uid == uid)
        )
        invoice = result.scalar_one_or_none()
        return invoice.as_dict() if invoice else None


async def update_invoice(
        uid: int,
        **kwargs
) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(TmpInvoice).where(TmpInvoice.uid == uid)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None

        for key, value in kwargs.items():
            setattr(invoice, key, value)

        await session.commit()
        return invoice.as_dict()


async def delete_invoice(uid: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            delete(TmpInvoice).where(TmpInvoice.uid == uid)
        )
        await session.commit()
        return result.rowcount > 0