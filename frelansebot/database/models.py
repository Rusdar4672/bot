from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    """Telegram-чат или канал, откуда собираем сообщения."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    """Найденный заказ или приглашение на работу."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    keywords_matched: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped["Source"] = relationship(backref="orders")


class SentNotification(Base):
    """Чтобы один и тот же заказ (по хешу) не слать пользователю повторно."""

    __tablename__ = "sent_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    """Пользователь бота — подписчик на уведомления."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    keywords: Mapped[str | None] = mapped_column(String(512), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
