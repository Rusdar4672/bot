import asyncio
import logging
import re

from aiogram import Bot

from collector.dedup import order_fingerprint
from collector.filters import (
    CATEGORY_KEYS,
    FILTER_CATEGORIES,
    FILTER_STACKS,
    STACK_KEYS,
)
from collector.parser import is_junk_content
from database.models import Order, Source
from services.formatter import send_order_messages

logger = logging.getLogger(__name__)

ORDER_GAP_SECONDS = 1.5
CATCHUP_INTERVAL = 180  # раз в 3 минуты догоняем непрочитанные свежие заказы


def _catalog_matches(text_lower: str, catalog: list[dict], selected: set[str]) -> bool:
    for item in catalog:
        if item["key"] not in selected:
            continue
        for word in item["match"]:
            token = word.lower()
            if len(token) <= 2:
                if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text_lower):
                    return True
            elif token in text_lower:
                return True
    return False


def order_matches_user_filters(order_text: str, user_keys: set[str], author: str | None = None) -> bool:
    if is_junk_content(order_text, author=author):
        return False
    if not user_keys:
        return True

    cat_keys = user_keys & CATEGORY_KEYS
    stack_keys = user_keys & STACK_KEYS
    text_lower = order_text.lower()

    if cat_keys and stack_keys:
        return _catalog_matches(text_lower, FILTER_CATEGORIES, cat_keys) and _catalog_matches(
            text_lower, FILTER_STACKS, stack_keys
        )
    if cat_keys:
        return _catalog_matches(text_lower, FILTER_CATEGORIES, cat_keys)
    if stack_keys:
        return _catalog_matches(text_lower, FILTER_STACKS, stack_keys)
    return True


def pick_orders_for_filters(
    recent: list[Order],
    fallback: list[Order],
    user_keys: set[str],
    *,
    limit: int = 5,
) -> list[Order]:
    """Сначала свежие под фильтр, если мало — добираем из окна 7–14 дней. Без дублей по хешу."""
    picked: list[Order] = []
    seen_hashes: set[str] = set()

    def base_hash(order: Order) -> str:
        digest = order.content_hash or order_fingerprint(order.text)
        return digest.split(":", 1)[0]

    def add_from(pool: list[Order]) -> None:
        for order in pool:
            if len(picked) >= limit:
                return
            if is_junk_content(order.text, author=order.author):
                continue
            if user_keys and not order_matches_user_filters(order.text, user_keys, author=order.author):
                continue
            digest = base_hash(order)
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            picked.append(order)

    add_from(recent)
    if len(picked) < limit:
        add_from(fallback)
    return picked


class Notifier:
    """Очередь уведомлений: заказы уходят по одному, без наложений и без повторных пушей."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self._queue: asyncio.Queue[tuple[Order, Source]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._catchup: asyncio.Task | None = None
        self._user_locks: dict[int, asyncio.Lock] = {}
        self._seen_queue: set[str] = set()

    def start(self) -> None:
        """Запускает воркер очереди и периодический догон непрочитанных заказов."""
        self._ensure_worker()
        if self._catchup is None or self._catchup.done():
            self._catchup = asyncio.create_task(self._catchup_loop(), name="notify-catchup")
            logger.info("Notifier auto-push started (live + catch-up every %ss)", CATCHUP_INTERVAL)

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_queue(), name="notify-queue")

    def _lock_for(self, telegram_id: int) -> asyncio.Lock:
        lock = self._user_locks.get(telegram_id)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[telegram_id] = lock
        return lock

    async def notify_new_order(self, order: Order, source: Source) -> None:
        digest = order.content_hash or order_fingerprint(order.text)
        if digest in self._seen_queue:
            return
        self._seen_queue.add(digest)
        # Не раздуваем set бесконечно
        if len(self._seen_queue) > 5000:
            self._seen_queue.clear()

        self._ensure_worker()
        await self._queue.put((order, source))
        logger.info(
            "Queued order #%s from %s (queue size=%s)",
            order.id,
            source.title,
            self._queue.qsize(),
        )

    async def push_unsent_recent(self, *, max_age_days: int | None = None, limit: int = 40) -> int:
        """Догоняет свежие заказы из БД, которые ещё не слали пользователям."""
        from config.settings import settings
        from database.engine import async_session
        from database.repository import Repository

        days = max_age_days if max_age_days is not None else settings.recent_order_days
        queued = 0

        async with async_session() as session:
            repo = Repository(session)
            orders = await repo.get_orders_in_age_range(
                min_age_days=0,
                max_age_days=days,
                limit=limit,
            )
            # От старых к новым — в чате сверху свежие
            for order in reversed(orders):
                if is_junk_content(order.text):
                    continue
                source = order.source
                if source is None:
                    continue
                digest = order.content_hash or order_fingerprint(order.text)
                if digest in self._seen_queue:
                    continue
                users = await repo.get_active_users()
                needs_send = False
                for user in users:
                    user_keys = (
                        {k.strip() for k in user.keywords.split(",") if k.strip()}
                        if user.keywords
                        else set()
                    )
                    if user_keys and not order_matches_user_filters(order.text, user_keys, author=order.author):
                        continue
                    if await repo.already_notified(user.telegram_id, digest):
                        continue
                    needs_send = True
                    break
                if needs_send:
                    await self.notify_new_order(order, source)
                    queued += 1

        if queued:
            logger.info("Catch-up queued %s unsent recent orders", queued)
        return queued

    async def _catchup_loop(self) -> None:
        # Сразу после старта — догнать то, что нашли в history scan без notify
        await asyncio.sleep(2)
        try:
            await self.push_unsent_recent()
        except Exception as e:
            logger.exception("Initial catch-up failed: %s", e)

        while True:
            await asyncio.sleep(CATCHUP_INTERVAL)
            try:
                await self.push_unsent_recent()
            except Exception as e:
                logger.exception("Periodic catch-up failed: %s", e)

    async def _run_queue(self) -> None:
        while True:
            order, source = await self._queue.get()
            try:
                await self._dispatch_order(order, source)
            except Exception as e:
                logger.exception("Failed to dispatch order #%s: %s", order.id, e)
            finally:
                self._queue.task_done()
                if not self._queue.empty():
                    await asyncio.sleep(ORDER_GAP_SECONDS)

    async def _dispatch_order(self, order: Order, source: Source) -> None:
        from database.engine import async_session
        from database.repository import Repository

        if is_junk_content(order.text, author=order.author):
            logger.info("Skip notify order #%s — junk content", order.id)
            return

        content_hash = order.content_hash or order_fingerprint(order.text)

        async with async_session() as session:
            repo = Repository(session)
            users = await repo.get_active_users()
            sent = 0

            for user in users:
                if user.keywords:
                    user_keys = {k.strip() for k in user.keywords.split(",") if k.strip()}
                    if user_keys and not order_matches_user_filters(
                        order.text, user_keys, author=order.author
                    ):
                        continue

                if await repo.already_notified(user.telegram_id, content_hash):
                    continue

                lock = self._lock_for(user.telegram_id)
                async with lock:
                    try:
                        await send_order_messages(self.bot, user.telegram_id, order, source)
                        await repo.mark_notified(user.telegram_id, content_hash, order.id)
                        await session.commit()
                        sent += 1
                        await asyncio.sleep(0.35)
                    except Exception as e:
                        logger.warning("Failed to notify user %s: %s", user.telegram_id, e)

            logger.info("Dispatched order #%s to %s user(s)", order.id, sent)
