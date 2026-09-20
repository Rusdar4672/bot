from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from bot.handlers.menu import send_main_menu
from bot.keyboards.main import BTN_HELP, BTN_OLDER, MAIN_KB, back_to_menu_keyboard
from database.engine import async_session
from database.repository import Repository

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    async with async_session() as session:
        repo = Repository(session)
        await repo.get_or_create_user(message.from_user.id, message.from_user.username)
        await session.commit()

    await bot.set_my_commands(
        [
            BotCommand(command="menu", description="Главное меню"),
            BotCommand(command="orders", description="Свежие заказы"),
            BotCommand(command="older", description="Архив старше недели"),
            BotCommand(command="filters", description="Настроить фильтры"),
            BotCommand(command="notify", description="Статус уведомлений"),
            BotCommand(command="help", description="Справка"),
        ]
    )

    await message.answer(
        "👋 Привет! Собираю фриланс-заказы из Telegram.\n"
        "Новые подходящие заказы приходят сами.",
        reply_markup=MAIN_KB,
    )
    await send_main_menu(message)


@router.message(Command("help"))
@router.message(lambda m: m.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Как это работает</b>\n\n"
        "1. Бот слушает чаты и каналы через Telethon\n"
        "2. Отсекает резюме, рекламу и трёп\n"
        "3. Подходящие заказы приходят тебе автоматически\n\n"
        "<b>Управление</b>\n"
        "🏠 Меню — панель управления\n"
        "⚙️ Фильтры — категории и стек\n"
        "📋 Заказы — свежие за неделю\n"
        f"📂 Архив / «{BTN_OLDER}» — старше недели\n"
        "🔔 Уведомления — пауза / возобновление пушей\n\n"
        "<b>Команды</b>\n"
        "/menu /orders /older /filters /notify /help",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
