import logging
from datetime import datetime, timezone, timedelta

from telethon import events
from telethon.tl.types import Channel, Chat, Message

from collector.dedup import order_fingerprint
from collector.parser import is_junk_content, parse_message
from collector.telethon_session import build_telegram_client, persist_string_session
from config.settings import settings
from database.engine import async_session
from database.repository import Repository
from services.notifier import Notifier

logger = logging.getLogger(__name__)


def _is_message_fresh(message: Message) -> bool:
    """True, если дата публикации сообщения не старше max_order_age_days."""
    published = getattr(message, "date", None)
    if published is None:
        return False

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    max_age = timedelta(days=settings.max_order_age_days)
    return datetime.now(timezone.utc) - published <= max_age


def _format_saved_tags(parsed) -> str:
    parts: list[str] = []
    if parsed.matched_keywords:
        parts.append(", ".join(parsed.matched_keywords))
    if parsed.job_type:
        parts.append(f"#{parsed.job_type}")
    if parsed.position:
        parts.append(parsed.position)
    if parsed.languages:
        parts.append(", ".join(parsed.languages))
    if parsed.hashtags:
        parts.append(" ".join(f"#{tag}" for tag in parsed.hashtags))
    return " | ".join(parts)[:512]


class MessageCollector:
    """Клиент Telethon — слушает чаты/каналы и сохраняет заказы."""

    def __init__(self, notifier: Notifier):
        self.client = build_telegram_client(settings.api_id, settings.api_hash)
        self.notifier = notifier

    async def start(self) -> None:
        await self.client.start(phone=settings.phone or None)
        persist_string_session(self.client)
        me = await self.client.get_me()
        logger.info("Collector started as %s", me.username or me.id)

        # Слушаем новые сообщения сразу — до скана истории
        @self.client.on(events.NewMessage())
        async def handler(event: events.NewMessage.Event) -> None:
            await self._process_message(event)

        logger.info("Listening for new messages (auto-notify ON)...")

        if settings.history_scan_limit > 0:
            await self.scan_recent_messages()
        else:
            logger.info("History scan skipped (history_scan_limit=0) — only new messages")

        # Догоняем свежие заказы, найденные без notify при скане
        try:
            await self.notifier.push_unsent_recent()
        except Exception as e:
            logger.warning("Post-scan catch-up failed: %s", e)

    async def scan_recent_messages(self) -> None:
        """Проверяет последние N сообщений во всех чатах и каналах."""
        limit = settings.history_scan_limit
        notify = settings.history_scan_notify
        max_age_days = settings.max_order_age_days
        logger.info(
            "Scanning last %s messages (max age %s days, notify=%s)...",
            limit,
            max_age_days,
            notify,
        )

        found = 0
        skipped_old = 0
        async for dialog in self.client.iter_dialogs():
            if not (dialog.is_channel or dialog.is_group):
                continue

            entity = dialog.entity
            if not isinstance(entity, (Channel, Chat)):
                continue

            title = dialog.title or ""
            try:
                async for message in self.client.iter_messages(entity, limit=limit):
                    if not _is_message_fresh(message):
                        skipped_old += 1
                        # Сообщения идут от новых к старым — дальше только старше
                        break
                    if await self._handle_text_message(
                        entity, dialog.id, message, notify=notify
                    ):
                        found += 1
            except Exception as e:
                logger.warning("Failed to scan %s: %s", title, e)

        logger.info(
            "History scan complete, found %s new orders, skipped %s old messages",
            found,
            skipped_old,
        )

    async def _process_message(self, event: events.NewMessage.Event) -> None:
        if not event.message:
            return

        # Игнорируем сервисные уведомления (вступления, закрепления и т.д.)
        if getattr(event.message, "action", None) is not None:
            return

        if not event.message.text:
            return

        chat = await event.get_chat()
        if not isinstance(chat, (Channel, Chat)):
            return

        await self._handle_text_message(chat, event.chat_id, event.message)

    async def _handle_text_message(
        self,
        chat: Channel | Chat,
        chat_id: int,
        message: Message,
        notify: bool = True,
    ) -> bool:
        """Сохраняет заказ, если сообщение подходит. Возвращает True при новом заказе."""
        if not message.text:
            return False

        if not _is_message_fresh(message):
            return False

        author = None
        sender = await message.get_sender()
        if sender:
            author = getattr(sender, "username", None) or str(getattr(sender, "id", ""))

        if is_junk_content(message.text, author=author):
            return False

        parsed = parse_message(message.text)
        if not parsed.is_order:
            return False

        title = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", None)
        content_hash = order_fingerprint(message.text)

        async with async_session() as session:
            repo = Repository(session)
            source = await repo.get_or_create_source(chat_id, title, username)

            if await repo.order_exists(source.id, message.id):
                return False

            # Тот же текст уже был в другом канале — не дублируем и не пушим снова
            existing = await repo.find_by_content_hash(content_hash)
            if existing is not None:
                logger.info(
                    "Skip duplicate order from %s (same as #%s)",
                    title,
                    existing.id,
                )
                return False

            link = self._build_message_link(username, chat_id, message.id)

            published_at = getattr(message, "date", None)
            if published_at is not None and published_at.tzinfo is not None:
                published_at = published_at.replace(tzinfo=None)

            order = await repo.create_order(
                source_id=source.id,
                message_id=message.id,
                text=message.text,
                author=author,
                link=link,
                keywords_matched=_format_saved_tags(parsed),
                published_at=published_at,
                content_hash=content_hash,
            )
            await session.commit()

            logger.info("New order #%s from %s", order.id, title)
            if notify:
                await self.notifier.notify_new_order(order, source)
            return True

    @staticmethod
    def _build_message_link(username: str | None, chat_id: int, message_id: int) -> str | None:
        if username:
            return f"https://t.me/{username}/{message_id}"

        cid = str(chat_id)
        if cid.startswith("-100"):
            cid = cid[4:]
        elif cid.startswith("-"):
            cid = cid[1:]
        return f"https://t.me/c/{cid}/{message_id}"

    async def sync_dialogs(self) -> list[dict]:
        """Возвращает список доступных чатов/каналов для добавления."""
        dialogs = []
        async for dialog in self.client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                entity = dialog.entity
                dialogs.append(
                    {
                        "id": dialog.id,
                        "title": dialog.title or "",
                        "username": getattr(entity, "username", None),
                    }
                )
        return dialogs

    async def run_until_disconnected(self) -> None:
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        await self.client.disconnect()