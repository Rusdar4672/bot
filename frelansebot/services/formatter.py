import html
import re

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from collector.extract import extract_amounts, extract_contacts, extract_job_meta
from database.models import Order, Source

TELEGRAM_MAX_LENGTH = 4096
SEP = "──────────────"

_MD_BOLD_US = re.compile(r"__(.+?)__", re.DOTALL)
_MD_STRIKE = re.compile(r"~~(.+?)~~", re.DOTALL)
_MD_CODE = re.compile(r"`([^`]+)`")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_STAR_WRAP = re.compile(r"\*{1,3}([^*\n]+)\*{1,3}")
_MD_STAR_BULLET = re.compile(r"(?m)^[ \t]*\*+[ \t]+")


def _strip_markdown(text: str) -> str:
    """Снимает markdown и вычищает все * из текста вакансии."""
    cleaned = text.replace("\r\n", "\n")
    cleaned = _MD_LINK.sub(r"\1", cleaned)
    cleaned = _MD_STAR_BULLET.sub("• ", cleaned)
    for _ in range(3):
        cleaned = _MD_STAR_WRAP.sub(r"\1", cleaned)
    cleaned = _MD_BOLD_US.sub(r"\1", cleaned)
    cleaned = _MD_STRIKE.sub(r"\1", cleaned)
    cleaned = _MD_CODE.sub(r"\1", cleaned)
    cleaned = cleaned.replace("*", "").replace("＊", "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def _author_line(author: str) -> str:
    if author.startswith("@") or author.isdigit():
        return f"👤 {html.escape(author)}"
    return f"👤 @{html.escape(author)}"


def _contact_html(value: str) -> str:
    escaped = html.escape(value)
    if value.startswith("@") and len(value) > 1:
        return f'<a href="https://t.me/{html.escape(value[1:], quote=True)}">{escaped}</a>'
    if value.startswith(("http://", "https://")):
        return f'<a href="{html.escape(value, quote=True)}">{escaped}</a>'
    if "@" in value and not value.startswith("+"):
        return f'<a href="mailto:{html.escape(value, quote=True)}">{escaped}</a>'
    return escaped


def _chips(meta, amounts: list[str]) -> list[str]:
    chips: list[str] = []
    if meta.job_type:
        chips.append(meta.job_type.capitalize())
    if meta.position:
        chips.append(meta.position)
    if meta.work_format:
        chips.append(meta.work_format.capitalize())
    if amounts:
        chips.append(amounts[0])
    return chips


def build_order_keyboard(order: Order, contacts) -> InlineKeyboardMarkup | None:
    buttons: list[list[InlineKeyboardButton]] = []

    target_url = None
    for tg in contacts.telegrams:
        if tg.startswith("@") and len(tg) > 1:
            target_url = f"https://t.me/{tg[1:]}"
            break
        if tg.startswith("https://t.me/"):
            target_url = tg
            break

    if not target_url and order.author:
        author = order.author.strip()
        if not author.isdigit():
            target_url = f"https://t.me/{author.lstrip('@')}"

    row: list[InlineKeyboardButton] = []
    if target_url:
        row.append(InlineKeyboardButton(text="💬 Написать", url=target_url))
    if order.link:
        row.append(InlineKeyboardButton(text="🔗 Открыть пост", url=order.link))
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def format_order_messages(
    order: Order,
    source: Source | None,
    *,
    heading: str = "📋 <b>Новый заказ</b>",
) -> list[str]:
    amounts = extract_amounts(order.text)
    contacts = extract_contacts(order.text)
    meta = extract_job_meta(order.text)
    source_title = source.title if source else "?"

    lines = [heading, SEP, f"📌 <b>{html.escape(source_title)}</b>"]

    meta_bits: list[str] = []
    if order.published_at:
        meta_bits.append(order.published_at.strftime("%d.%m %H:%M"))
    if order.author:
        meta_bits.append(_author_line(order.author))
    if meta_bits:
        lines.append(" · ".join(meta_bits))

    chips = _chips(meta, amounts)
    if chips:
        lines.append(" · ".join(html.escape(c) for c in chips))

    detail_lines: list[str] = []
    if meta.languages:
        detail_lines.append(f"🛠 <b>Языки:</b> {html.escape(', '.join(meta.languages))}")
    if meta.technologies:
        detail_lines.append(f"⚙️ <b>Стек:</b> {html.escape(', '.join(meta.technologies))}")
    if amounts and len(amounts) > 1:
        detail_lines.append(f"💰 <b>Сумма:</b> {html.escape(', '.join(amounts))}")
    if meta.hashtags:
        detail_lines.append(" ".join(f"#{html.escape(tag)}" for tag in meta.hashtags[:8]))
    if detail_lines:
        lines.append("")
        lines.extend(detail_lines)

    lines.extend(["", SEP, ""])
    header = "\n".join(lines)
    body = html.escape(_strip_markdown(order.text.strip()))

    footer_parts: list[str] = []
    if contacts.all():
        footer_parts.append(SEP)
        footer_parts.append("📞 <b>Контакты</b>")
        footer_parts.extend(f"• {_contact_html(item)}" for item in contacts.all())
    footer = ("\n\n" + "\n".join(footer_parts)) if footer_parts else ""

    if len(header) + len(body) + len(footer) <= TELEGRAM_MAX_LENGTH:
        return [header + body + footer]

    messages: list[str] = []
    first_limit = max(400, TELEGRAM_MAX_LENGTH - len(header) - 20)
    messages.append(header + body[:first_limit])
    rest = body[first_limit:]
    while rest:
        chunk = rest[: TELEGRAM_MAX_LENGTH - 20]
        rest = rest[len(chunk) :]
        messages.append(chunk)
    if footer_parts:
        messages.append("\n".join(footer_parts))
    return messages


def format_order_card(
    order: Order,
    source: Source | None,
    *,
    heading: str = "📋 <b>Новый заказ</b>",
    body_limit: int | None = None,
) -> str:
    messages = format_order_messages(order, source, heading=heading)
    if body_limit is not None:
        full = messages[0]
        return full if len(full) <= body_limit else full[: body_limit - 3] + "..."
    return messages[0] if len(messages) == 1 else "\n\n".join(messages)


async def send_order_messages(
    bot: Bot,
    chat_id: int,
    order: Order,
    source: Source | None,
    *,
    heading: str = "📋 <b>Новый заказ</b>",
) -> None:
    contacts = extract_contacts(order.text)
    keyboard = build_order_keyboard(order, contacts)
    messages = format_order_messages(order, source, heading=heading)
    total = len(messages)

    for idx, msg in enumerate(messages):
        await bot.send_message(
            chat_id,
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard if idx == total - 1 else None,
        )
