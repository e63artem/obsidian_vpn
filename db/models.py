from typing import cast

from sqlalchemy import String, Float, ForeignKey, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Mapper
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession

from config import Config

engine = create_async_engine(url=Config.DB_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    def as_dict(self) -> dict:
        mapper: Mapper = cast(Mapper, inspect(self).mapper)
        return {
            column.key: getattr(self, column.key)
            for column in mapper.column_attrs
        }

    def __repr__(self):
        return self.as_dict()


class User(Base):
    __tablename__ = 'users'

    uid: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(11), nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    pay_date_time: Mapped[str] = mapped_column(String(150), nullable=True)
    subscribe_days_left: Mapped[int] = mapped_column(default=0)
    referrer: Mapped[int] = mapped_column(nullable=True)
    is_trial: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=True)
    credits_on_account: Mapped[int] = mapped_column(nullable=False, default=0)


class VpnConfig(Base):
    __tablename__ = "vpn_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[str] = mapped_column(String, unique=True)  # ID в Google Drive
    filename: Mapped[str] = mapped_column(String)
    assigned: Mapped[bool] = mapped_column(default=False)
    expired: Mapped[str] = mapped_column(String(12), nullable=True)  # Дата истечения конфигурации
    device: Mapped[str] = mapped_column(String(30), nullable=True)
    uid: Mapped[int | None] = mapped_column(ForeignKey("users.uid"), nullable=True)


class TmpInvoice(Base):
    __tablename__ = "tmp_invoices"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uid: Mapped[int] = mapped_column(ForeignKey("users.uid"))
    config_id: Mapped[int] = mapped_column(ForeignKey("vpn_configs.id"), nullable=True, default=None)
    summary: Mapped[int] = mapped_column(nullable=True)
    use_credits: Mapped[bool] = mapped_column(default=False, nullable=True)
    number_of_configs: Mapped[int] = mapped_column(default=1)
    days_to_increase: Mapped[int] = mapped_column(nullable=True)
    paid: Mapped[bool] = mapped_column(default=False)
    paid_at: Mapped[str] = mapped_column(String(12), nullable=True)
    created_at: Mapped[str] = mapped_column(String(12), nullable=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
