import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main import (
    BTN_FILTERS,
    BTN_OLDER,
    BTN_ORDERS,
    MAIN_KB,
    back_to_menu_keyboard,
    filters_keyboard,
    format_filter_labels,
    older_orders_keyboard,
)
from config.settings import settings
from database.engine import async_session
from database.repository import Repository
from services.formatter import send_order_messages
from services.notifier import order_matches_user_filters, pick_orders_for_filters

router = Router()
logger = logging.getLogger(__name__)

# Сколько архивных заказов отдаём за раз (все подходящие, но с потолком от флуда)
OLDER_ORDERS_LIMIT = 30


def _parse_user_keys(keywords: str | None) -> set[str]:
    if not keywords:
        return set()
    return {k.strip() for k in keywords.split(",") if k.strip()}


async def _load_older_filtered_orders(telegram_id: int, username: str | None):
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(telegram_id, username)
        await session.commit()
        user_keys = _parse_user_keys(user.keywords)

        pool = await repo.get_orders_in_age_range(
            min_age_days=settings.recent_order_days,
            max_age_days=settings.fallback_order_days,
            limit=300,
        )
        orders = pick_orders_for_filters([], pool, user_keys, limit=OLDER_ORDERS_LIMIT)
        total_matched = sum(
            1 for o in pool if order_matches_user_filters(o.text, user_keys, author=o.author)
        )
        return orders, total_matched, user_keys


async def _send_older_orders(bot: Bot, chat_id: int, telegram_id: int, username: str | None) -> None:
    orders, total_matched, user_keys = await _load_older_filtered_orders(telegram_id, username)

    if not orders:
        await bot.send_message(
            chat_id,
            "За неделю–две по твоим фильтрам архивных заказов нет.\n"
            "Попробуй ослабить фильтры или загляни позже.",
        )
        return

    shown = len(orders)
    await bot.send_message(
        chat_id,
        f"👀 <b>Архив под твои фильтры</b>\n"
        f"Заказы старше {settings.recent_order_days} дней "
        f"(до {settings.fallback_order_days} дн.).\n"
        f"Найдено: <b>{total_matched}</b>"
        + (f", показываю {shown}" if total_matched > shown else "")
        + ".",
        parse_mode="HTML",
    )

    for order in orders:
        await send_order_messages(
            bot,
            chat_id,
            order,
            order.source,
            heading=f"📋 <b>Заказ #{order.id}</b> · архив",
        )
        await asyncio.sleep(0.4)


@router.message(Command("orders"))
@router.message(F.text == BTN_ORDERS)
async def cmd_orders(message: Message, bot: Bot) -> None:
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(message.from_user.id, message.from_user.username)
        await session.commit()
        user_keys = _parse_user_keys(user.keywords)

        recent_days = settings.recent_order_days

        recent = await repo.get_orders_in_age_range(
            min_age_days=0,
            max_age_days=recent_days,
            limit=100,
        )
        # Свежие только; архив — отдельной кнопкой «Посмотреть»
        orders = pick_orders_for_filters(recent, [], user_keys, limit=5)

        older_pool = await repo.get_orders_in_age_range(
            min_age_days=recent_days,
            max_age_days=settings.fallback_order_days,
            limit=100,
        )
        older_count = sum(
            1 for o in older_pool if order_matches_user_filters(o.text, user_keys, author=o.author)
        )

    if not orders:
        text = (
            "По твоим фильтрам нет свежих заказов за последнюю неделю.\n"
        )
        if older_count:
            text += (
                f"Зато в архиве (старше недели) есть <b>{older_count}</b> — "
                f"нажми «{BTN_OLDER}»."
            )
            await message.answer(text, parse_mode="HTML", reply_markup=MAIN_KB)
            await message.answer(
                "Открыть архив:",
                reply_markup=older_orders_keyboard(),
            )
        else:
            text += "Подожди новые посты или ослабь фильтры в «⚙️ Фильтры»."
            await message.answer(text, parse_mode="HTML", reply_markup=MAIN_KB)
        return

    for order in orders:
        await send_order_messages(
            bot,
            message.chat.id,
            order,
            order.source,
            heading=f"📋 <b>Заказ #{order.id}</b>",
        )

    if older_count:
        await message.answer(
            f"Ещё <b>{older_count}</b> подходящих заказов старше недели — кнопка «{BTN_OLDER}».",
            parse_mode="HTML",
            reply_markup=MAIN_KB,
        )
        await message.answer(
            "Или открой архив здесь:",
            reply_markup=older_orders_keyboard(),
        )
    else:
        await message.answer("Готово.", reply_markup=MAIN_KB)


@router.message(Command("older"))
@router.message(F.text == BTN_OLDER)
async def cmd_older_orders(message: Message, bot: Bot) -> None:
    await message.answer("Ищу заказы старше недели по твоим фильтрам…", reply_markup=MAIN_KB)
    await _send_older_orders(bot, message.chat.id, message.from_user.id, message.from_user.username)


@router.callback_query(F.data == "orders:older")
async def cb_older_orders(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    await callback.message.answer("Ищу заказы старше недели по твоим фильтрам…")
    await _send_older_orders(
        bot,
        callback.message.chat.id,
        callback.from_user.id,
        callback.from_user.username,
    )


def _filters_text(active: set[str]) -> str:
    return (
        "⚙️ <b>Настройка фильтров</b>\n\n"
        "Отметь категории и/или стек.\n"
        "Нажми ещё раз — снять ✅.\n\n"
        f"Сейчас активны: <b>{format_filter_labels(active)}</b>"
    )


async def _edit_filters_menu(callback: CallbackQuery, active: set[str]) -> None:
    text = _filters_text(active)
    markup = filters_keyboard(active)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return
        logger.warning("Failed to edit filters menu: %s", e)
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(Command("filters"))
@router.message(F.text == BTN_FILTERS)
async def cmd_filters(message: Message) -> None:
    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(message.from_user.id, message.from_user.username)
        await session.commit()
        active = _parse_user_keys(user.keywords)

    await message.answer(
        _filters_text(active),
        parse_mode="HTML",
        reply_markup=filters_keyboard(active),
    )


@router.callback_query(F.data.startswith("flt:"))
async def cb_filter_toggle(callback: CallbackQuery) -> None:
    action = callback.data.split(":", 1)[1]
    logger.info("Filter callback from %s: %s", callback.from_user.id, action)

    if action == "noop":
        await callback.answer()
        return

    async with async_session() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user(callback.from_user.id, callback.from_user.username)
        active = _parse_user_keys(user.keywords)

        if action == "reset":
            active = set()
            user.keywords = ""
            await session.commit()
            await _edit_filters_menu(callback, active)
            await callback.answer("Фильтры сброшены")
            return

        if action == "done":
            await session.commit()
            label = format_filter_labels(active)
            try:
                await callback.message.edit_text(
                    f"✅ <b>Фильтры сохранены!</b>\n\n"
                    f"Активно: <b>{label}</b>\n\n"
                    "Если выбраны и категории, и стеки — заказ должен подойти и по теме, и по стеку.\n"
                    "Чтобы изменить — /filters или «⚙️ Фильтры».",
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard(),
                )
            except TelegramBadRequest as e:
                logger.warning("Failed to close filters menu: %s", e)
            await callback.answer("Фильтры сохранены!")
            return

        if action in active:
            active.discard(action)
        else:
            active.add(action)

        user.keywords = ",".join(sorted(active)) if active else ""
        await session.commit()

    await _edit_filters_menu(callback, active)
    await callback.answer()
