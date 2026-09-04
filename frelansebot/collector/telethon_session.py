"""Telethon-сессия без SQLite-лока: StringSession в файле."""

from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SQLITE_SESSION = ROOT / "collector_session_new"
STRING_SESSION_FILE = ROOT / "collector_session_new.session.txt"


def build_telegram_client(api_id: int, api_hash: str) -> TelegramClient:
    if STRING_SESSION_FILE.exists():
        data = STRING_SESSION_FILE.read_text(encoding="utf-8").strip()
        if data:
            logger.info("Telethon session: StringSession (no sqlite lock)")
            return TelegramClient(StringSession(data), api_id, api_hash)

    logger.info("Telethon session: sqlite %s.session (will migrate after login)", SQLITE_SESSION.name)
    return TelegramClient(str(SQLITE_SESSION), api_id, api_hash)


def persist_string_session(client: TelegramClient) -> None:
    session_str = StringSession.save(client.session)
    if not session_str:
        return
    STRING_SESSION_FILE.write_text(session_str, encoding="utf-8")
    logger.info("Saved StringSession to %s", STRING_SESSION_FILE.name)
