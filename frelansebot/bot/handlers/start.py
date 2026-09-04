from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.main import BTN_HELP, BTN_OLDER, MAIN_KB
from database.engine import async_session
from database.repository import Repository

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        repo = Repository(session)
        await repo.get_or_create_user(message.from_user.id, message.from_user.username)
        await session.commit()

    await message.answer(
        "👋 Привет! Я бот для сбора фриланс-заказов из Telegram-чатов и каналов.\n\n"
        "Я автоматически мониторю подключённые источники и присылаю тебе "
        "новые заказы и приглашения на работу.\n\n"
        "Используй кнопки ниже или команды:\n"
        "/orders — свежие заказы за неделю\n"
        f"/older или «{BTN_OLDER}» — архив старше недели\n"
        "/filters — настроить фильтры\n"
        "/help — справка",
        reply_markup=MAIN_KB,
    )


@router.message(Command("help"))
@router.message(lambda m: m.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Как это работает</b>\n\n"
        "1. Администратор подключает Telegram-аккаунт (Telethon) к чатам и каналам\n"
        "2. Бот анализирует новые сообщения по ключевым словам\n"
        "3. Найденные заказы сохраняются и рассылаются подписчикам\n\n"
        "<b>Команды</b>\n"
        "/orders — свежие заказы за неделю (по фильтрам)\n"
        f"/older или «{BTN_OLDER}» — все подходящие старше недели\n"
        "/filters — настроить фильтры по категориям и стеку\n\n"
        "<b>Для администраторов</b>\n"
        "/stats — статистика",
        parse_mode="HTML",
        reply_markup=MAIN_KB,
    )
