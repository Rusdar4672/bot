"""
Одноразовая авторизация Telethon-коллектора.

Запуск:
    python scripts/auth_collector.py

Telegram пришлёт код — введи его в терминале.
После успешного входа можно запускать бота: python main.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.telethon_session import (
    STRING_SESSION_FILE,
    build_telegram_client,
    persist_string_session,
)
from config.settings import settings


async def main() -> None:
    client = build_telegram_client(settings.api_id, settings.api_hash)
    await client.start(phone=settings.phone or None)
    persist_string_session(client)
    me = await client.get_me()
    print(f"\n✅ Авторизация успешна: {me.username or me.id}")
    print(f"Session сохранён в {STRING_SESSION_FILE.name}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
