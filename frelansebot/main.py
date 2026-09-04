"""
Freelance Order Bot — точка входа.

Запускает одновременно:
  1. Telegram-бот (aiogram) — интерфейс для пользователей
  2. Коллектор (Telethon) — мониторинг чатов и каналов
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot

from bot.app import create_bot
from collector.client import MessageCollector
from config.settings import settings
from database.engine import init_db
from services.notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
PID_FILE = Path(__file__).resolve().parent / "bot.pid"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _acquire_pid_lock() -> None:
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            old_pid = 0
        if old_pid != os.getpid() and _pid_alive(old_pid):
            raise SystemExit(
                f"Уже запущен python main.py (pid {old_pid}). "
                "Останови его, иначе Telethon снова залочит session."
            )
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _release_pid_lock() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass


async def main() -> None:
    logger.info("Initializing database...")
    await init_db()

    bot, dp = create_bot()
    notifier = Notifier(bot)
    collector = MessageCollector(notifier)

    logger.info("Starting collector...")
    await collector.start()

    logger.info("Starting bot polling...")
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            collector.run_until_disconnected(),
        )
    finally:
        await collector.stop()
        await bot.session.close()


if __name__ == "__main__":
    _acquire_pid_lock()
    try:
        asyncio.run(main())
    finally:
        _release_pid_lock()
