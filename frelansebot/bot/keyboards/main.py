from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from collector.filters import FILTER_CATEGORIES, FILTER_STACKS

# Reply-кнопки — тексты должны совпадать с хендлерами
BTN_MENU = "🏠 Меню"
BTN_FILTERS = "⚙️ Фильтры"
BTN_ORDERS = "📋 Заказы"
BTN_OLDER = "📂 Архив"
BTN_NOTIFY = "🔔 Уведомления"
BTN_HELP = "ℹ️ Помощь"

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_MENU)],
        [
            KeyboardButton(text=BTN_FILTERS),
            KeyboardButton(text=BTN_ORDERS),
        ],
        [
            KeyboardButton(text=BTN_OLDER),
            KeyboardButton(text=BTN_NOTIFY),
        ],
        [KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def main_menu_keyboard(*, notify_on: bool = True) -> InlineKeyboardMarkup:
    """Главное inline-меню управления (в стиле lead-ботов)."""
    notify_label = "🔔 Уведомления: Вкл ✅" if notify_on else "🔕 Уведомления: Выкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настроить фильтры", callback_data="menu:filters")],
            [
                InlineKeyboardButton(text="📋 Свежие заказы", callback_data="menu:orders"),
                InlineKeyboardButton(text="📂 Архив", callback_data="menu:older"),
            ],
            [InlineKeyboardButton(text=notify_label, callback_data="menu:notify")],
            [InlineKeyboardButton(text="ℹ️ Справка", callback_data="menu:help")],
        ]
    )


def older_orders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 Посмотреть архив старше недели",
                    callback_data="orders:older",
                )
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu:home")],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="menu:home")]]
    )


def filters_keyboard(active_keys: set[str]) -> InlineKeyboardMarkup:
    """Категории + стеки + возврат в меню."""
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton(text="📂 Категории", callback_data="flt:noop")])
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

    rows.append([InlineKeyboardButton(text="🛠 Стек", callback_data="flt:noop")])
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
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_filter_labels(active_keys: set[str]) -> str:
    if not active_keys:
        return "не выбраны (приходят все заказы)"
    labels: list[str] = []
    for cat in FILTER_CATEGORIES:
        if cat["key"] in active_keys:
            labels.append(str(cat["label"]))
    for stack in FILTER_STACKS:
        if stack["key"] in active_keys:
            labels.append(str(stack["label"]))
    return ", ".join(labels) if labels else "не выбраны (приходят все заказы)"
