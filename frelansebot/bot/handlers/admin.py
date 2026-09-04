from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings
from database.engine import async_session
from database.repository import Repository

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return

    async with async_session() as session:
        repo = Repository(session)
        sources = await repo.get_all_sources()
        orders = await repo.get_recent_orders(limit=1000)
        users = await repo.get_active_users()

    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Источников: {len(sources)}\n"
        f"Заказов: {len(orders)}+\n"
        f"Подписчиков: {len(users)}",
        parse_mode="HTML",
    )
