from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from collector.filters import FILTER_CATEGORIES, FILTER_STACKS

# Текст кнопки архива — должен совпадать с хендлером в orders.py
BTN_OLDER = "Посмотреть"
BTN_ORDERS = "📋 Последние заказы"
BTN_FILTERS = "⚙️ Мои фильтры"
BTN_HELP = "ℹ️ Помощь"

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=BTN_ORDERS),
            KeyboardButton(text=BTN_OLDER),
        ],
        [
            KeyboardButton(text=BTN_FILTERS),
            KeyboardButton(text=BTN_HELP),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def admin_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ORDERS)
    builder.button(text=BTN_OLDER)
    builder.button(text=BTN_FILTERS)
    builder.button(text=BTN_HELP)
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)


def older_orders_keyboard() -> InlineKeyboardMarkup:
    """Кнопка после свежих заказов — открыть архив под фильтры."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Посмотреть старше недели",
                    callback_data="orders:older",
                )
            ]
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]]
    )


def filters_keyboard(active_keys: set[str]) -> InlineKeyboardMarkup:
    """Одно меню: категории + стеки, без переключения страниц."""
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [InlineKeyboardButton(text="📂 Категории", callback_data="flt:noop")]
    )
    for cat in FILTER_CATEGORIES:
        key = str(cat["key"])
        check = "✅ " if key in active_keys else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{check}{cat['label']}",
                    callback_data=f"flt:{key}",
                )
            ]
        )

    rows.append(
        [InlineKeyboardButton(text="🛠 Стек", callback_data="flt:noop")]
    )
    stack_row: list[InlineKeyboardButton] = []
    for stack in FILTER_STACKS:
        key = str(stack["key"])
        check = "✅ " if key in active_keys else ""
        stack_row.append(
            InlineKeyboardButton(
                text=f"{check}{stack['label']}",
                callback_data=f"flt:{key}",
            )
        )
        if len(stack_row) == 2:
            rows.append(stack_row)
            stack_row = []
    if stack_row:
        rows.append(stack_row)

    rows.append(
        [
            InlineKeyboardButton(text="🔄 Сбросить", callback_data="flt:reset"),
            InlineKeyboardButton(text="✅ Готово", callback_data="flt:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
