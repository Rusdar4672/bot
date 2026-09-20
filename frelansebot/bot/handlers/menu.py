"""Главное меню управления ботом (inline + reply)."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main import (
    BTN_MENU,
    BTN_NOTIFY,
    MAIN_KB,
    format_filter_labels,
    main_menu_keyboard,
)
from database.engine import async_session
from database.repository import Repository

router = Router()


def _parse_keys(keywords: str | None) -> set[str]:
    if not keywords:
        return set()
    return {k.strip() for k in keywords.split(",") if k.strip()}


def _menu_text(*, notify_on: bool, active: set[str]) -> str:
    status = "✅ включены" if notify_on else "⏸ выключены"
    return (
        "🏠 <b>Управление ботом</b>\n\n"
        f"Уведомления: <b>{status}</b>\n"
        f"Фильтры: <b>{format_filter_labels(active)}</b>\n\n"
        "Выбери действие кнопками ниже."
    )


async def _load_user_state(telegram_id: int, username: str | None) -> tuple[bool, set[str]]:
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(telegram_id, username)
        await session.commit()
        return bool(user.is_active), _parse_keys(user.keywords)


async def send_main_menu(message: Message, *, with_reply_kb: bool = False) -> None:
    notify_on, active = await _load_user_state(
        message.from_user.id, message.from_user.username
    )
    text = _menu_text(notify_on=notify_on, active=active)
    inline = main_menu_keyboard(notify_on=notify_on)
    if with_reply_kb:
        await message.answer(text, parse_mode="HTML", reply_markup=MAIN_KB)
        await message.answer("Панель:", reply_markup=inline)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=inline)


@router.message(Command("menu"))
@router.message(F.text == BTN_MENU)
async def cmd_menu(message: Message) -> None:
    await send_main_menu(message, with_reply_kb=True)


@router.message(Command("notify"))
@router.message(F.text == BTN_NOTIFY)
async def cmd_notify_status(message: Message) -> None:
    notify_on, active = await _load_user_state(
        message.from_user.id, message.from_user.username
    )
    status = "включены ✅" if notify_on else "выключены ⏸"
    await message.answer(
        f"🔔 Уведомления сейчас <b>{status}</b>.\n"
        f"Фильтры: <b>{format_filter_labels(active)}</b>\n\n"
        "Переключить можно кнопкой ниже.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(notify_on=notify_on),
    )


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery) -> None:
    notify_on, active = await _load_user_state(
        callback.from_user.id, callback.from_user.username
    )
    await callback.answer()
    try:
        await callback.message.edit_text(
            _menu_text(notify_on=notify_on, active=active),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(notify_on=notify_on),
        )
    except Exception:
        await callback.message.answer(
            _menu_text(notify_on=notify_on, active=active),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(notify_on=notify_on),
        )


@router.callback_query(F.data == "menu:notify")
async def cb_toggle_notify(callback: CallbackQuery) -> None:
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(
            callback.from_user.id, callback.from_user.username
        )
        user.is_active = not bool(user.is_active)
        await session.commit()
        notify_on = bool(user.is_active)
        active = _parse_keys(user.keywords)

    await callback.answer("Уведомления включены" if notify_on else "Уведомления выключены")
    try:
        await callback.message.edit_text(
            _menu_text(notify_on=notify_on, active=active),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(notify_on=notify_on),
        )
    except Exception:
        await callback.message.answer(
            _menu_text(notify_on=notify_on, active=active),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(notify_on=notify_on),
        )


@router.callback_query(F.data == "menu:filters")
async def cb_menu_filters(callback: CallbackQuery) -> None:
    from bot.handlers.orders import _filters_text, _parse_user_keys
    from bot.keyboards.main import filters_keyboard

    await callback.answer()
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(
            callback.from_user.id, callback.from_user.username
        )
        await session.commit()
        active = _parse_user_keys(user.keywords)

    try:
        await callback.message.edit_text(
            _filters_text(active),
            parse_mode="HTML",
            reply_markup=filters_keyboard(active),
        )
    except Exception:
        await callback.message.answer(
            _filters_text(active),
            parse_mode="HTML",
            reply_markup=filters_keyboard(active),
        )


@router.callback_query(F.data == "menu:orders")
async def cb_menu_orders(callback: CallbackQuery, bot) -> None:
    await callback.answer()
    await _run_orders_from_callback(callback, bot)


async def _run_orders_from_callback(callback: CallbackQuery, bot) -> None:
    from bot.handlers.orders import _parse_user_keys
    from config.settings import settings
    from services.formatter import send_order_messages
    from services.notifier import order_matches_user_filters, pick_orders_for_filters
    from bot.keyboards.main import BTN_OLDER, MAIN_KB, older_orders_keyboard

    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(
            callback.from_user.id, callback.from_user.username
        )
        await session.commit()
        user_keys = _parse_user_keys(user.keywords)
        recent_days = settings.recent_order_days
        recent = await repo.get_orders_in_age_range(
            min_age_days=0, max_age_days=recent_days, limit=100
        )
        orders = pick_orders_for_filters(recent, [], user_keys, limit=5)
        older_pool = await repo.get_orders_in_age_range(
            min_age_days=recent_days,
            max_age_days=settings.fallback_order_days,
            limit=100,
        )
        older_count = sum(
            1
            for o in older_pool
            if order_matches_user_filters(o.text, user_keys, author=o.author)
        )

    chat_id = callback.message.chat.id
    if not orders:
        text = "По твоим фильтрам нет свежих заказов за последнюю неделю.\n"
        if older_count:
            text += (
                f"Зато в архиве есть <b>{older_count}</b> — нажми «{BTN_OLDER}»."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=MAIN_KB)
            await bot.send_message(chat_id, "Открыть архив:", reply_markup=older_orders_keyboard())
        else:
            text += "Подожди новые посты или ослабь фильтры."
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=MAIN_KB)
        return

    for order in orders:
        await send_order_messages(
            bot, chat_id, order, order.source, heading=f"📋 <b>Заказ #{order.id}</b>"
        )
    if older_count:
        await bot.send_message(
            chat_id,
            f"Ещё <b>{older_count}</b> в архиве — «{BTN_OLDER}».",
            parse_mode="HTML",
            reply_markup=older_orders_keyboard(),
        )


@router.callback_query(F.data == "menu:older")
async def cb_menu_older(callback: CallbackQuery, bot) -> None:
    from bot.handlers.orders import _send_older_orders

    await callback.answer()
    await callback.message.answer("Ищу заказы старше недели…")
    await _send_older_orders(
        bot,
        callback.message.chat.id,
        callback.from_user.id,
        callback.from_user.username,
    )


@router.callback_query(F.data == "menu:help")
async def cb_menu_help(callback: CallbackQuery) -> None:
    from bot.keyboards.main import BTN_OLDER, back_to_menu_keyboard

    await callback.answer()
    text = (
        "<b>Как это работает</b>\n\n"
        "1. Бот слушает чаты и каналы\n"
        "2. Отсекает резюме, рекламу и трёп\n"
        "3. Подходящие заказы приходят автоматически\n\n"
        "<b>Управление</b>\n"
        "🏠 Меню · ⚙️ Фильтры · 📋 Заказы\n"
        f"📂 Архив · 🔔 Уведомления · ℹ️ Помощь"
    )
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=back_to_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=back_to_menu_keyboard()
        )
