from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from collector.dedup import order_fingerprint
from config.settings import settings
from database.models import Base, Order

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.execute(text("PRAGMA table_info(orders)"))
        columns = {row[1] for row in result.fetchall()}
        if "published_at" not in columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN published_at DATETIME"))
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_published_at ON orders (published_at)")
            )
        if "content_hash" not in columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN content_hash VARCHAR(64)"))
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_content_hash ON orders (content_hash)")
            )

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.content_hash.is_(None)))
        orders = list(result.scalars().all())
        seen: set[str] = set()
        for order in orders:
            digest = order_fingerprint(order.text)
            if digest in seen:
                order.content_hash = f"{digest}:{order.id}"
            else:
                order.content_hash = digest
                seen.add(digest)
        if orders:
            await session.commit()
