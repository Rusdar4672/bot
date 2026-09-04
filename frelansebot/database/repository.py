from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from collector.dedup import order_fingerprint
from database.models import Order, SentNotification, Source, User


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Sources ---

    async def get_or_create_source(
        self, chat_id: int, title: str = "", username: str | None = None
    ) -> Source:
        result = await self.session.execute(
            select(Source).where(Source.chat_id == chat_id)
        )
        source = result.scalar_one_or_none()
        if source:
            source.title = title or source.title
            source.username = username or source.username
            return source

        source = Source(chat_id=chat_id, title=title, username=username)
        self.session.add(source)
        await self.session.flush()
        return source

    async def get_active_sources(self) -> list[Source]:
        result = await self.session.execute(
            select(Source).where(Source.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_all_sources(self) -> list[Source]:
        result = await self.session.execute(select(Source))
        return list(result.scalars().all())

    # --- Orders ---

    async def order_exists(self, source_id: int, message_id: int) -> bool:
        result = await self.session.execute(
            select(Order.id).where(
                Order.source_id == source_id,
                Order.message_id == message_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def find_by_content_hash(self, content_hash: str) -> Order | None:
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.source))
            .where(Order.content_hash == content_hash)
            .order_by(Order.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_order(
        self,
        source_id: int,
        message_id: int,
        text: str,
        author: str | None = None,
        link: str | None = None,
        keywords_matched: str | None = None,
        published_at=None,
        content_hash: str | None = None,
    ) -> Order:
        order = Order(
            source_id=source_id,
            message_id=message_id,
            text=text,
            author=author,
            link=link,
            keywords_matched=keywords_matched,
            published_at=published_at,
            content_hash=content_hash or order_fingerprint(text),
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_recent_orders(self, limit: int = 10) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.source))
            .order_by(Order.published_at.desc().nullslast(), Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_orders_in_age_range(
        self,
        *,
        min_age_days: int = 0,
        max_age_days: int = 14,
        limit: int = 200,
    ) -> list[Order]:
        now = datetime.utcnow()
        newest = now - timedelta(days=min_age_days)
        oldest = now - timedelta(days=max_age_days)
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.source))
            .where(
                Order.published_at.is_not(None),
                Order.published_at >= oldest,
                Order.published_at <= newest,
            )
            .order_by(Order.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # --- Notifications ---

    async def already_notified(self, telegram_id: int, content_hash: str) -> bool:
        result = await self.session.execute(
            select(SentNotification.id).where(
                SentNotification.telegram_id == telegram_id,
                SentNotification.content_hash == content_hash,
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_notified(
        self, telegram_id: int, content_hash: str, order_id: int | None = None
    ) -> None:
        if await self.already_notified(telegram_id, content_hash):
            return
        self.session.add(
            SentNotification(
                telegram_id=telegram_id,
                content_hash=content_hash,
                order_id=order_id,
            )
        )
        await self.session.flush()

    # --- Users ---

    async def get_or_create_user(
        self, telegram_id: int, username: str | None = None
    ) -> User:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.username = username or user.username
            return user

        user = User(telegram_id=telegram_id, username=username)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_active_users(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def set_user_keywords(self, telegram_id: int, keywords: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.keywords = keywords
        return user
