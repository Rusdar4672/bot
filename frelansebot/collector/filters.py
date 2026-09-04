import re

# Маркеры резюме и самопиара. Только фразы от исполнителя, не требования вакансии.
RESUME_STOP_PATTERNS: list[str] = [
    r"\bрезюме\b",
    r"#резюме\b",
    r"сайт[- ]?резюме",
    r"\bcv\b",
    r"\bresume\b",
    r"\bищу работу\b",
    r"\bищу заказы\b",
    r"\bищу заказ\b",
    r"\bищу проект\b",
    r"\bищу проекты\b",
    r"\bищу подработк\w*",
    r"\bищу позицию\b",
    r"\bищу ваканси\w*",
    r"\bрассматриваю предложени\w*",
    r"\bготов к работе\b",
    r"\bготова к работе\b",
    r"\bобо мне\b",
    r"\bо себе\b",
    r"\bосновн\w*\s+специализаци\w*",
    r"\bмо[её] портфолио\b",
    r"\bмое портфолио\b",
    r"\bмои работы\b",
    r"\bмои навыки\b",
    r"\bмоя ставка\b",
    r"\bожидания по\s*(зп|зарплат\w*)",
    r"\bжелаемая\s*(зп|зарплат\w*)",
    r"\bключ[её]вые результаты\b",
    r"\bвозьму заказ\b",
    r"\bвозьму проект\b",
    r"\bвыполню\b",
    r"\bсделаю сайт\b",
    r"\bпредлагаю услуги\b",
    r"\bоказываю услуги\b",
    r"\bменя зовут\b",
    r"\bимею опыт\b",
    r"\bзанимаюсь\b",
    r"\bоткрыт[ао]\s+к\s+предложен",
    r"\bрассмотрю варианты\b",
    r"\bopen to work\b",
    r"\bhire me\b",
    r"\blooking for (a )?job\b",
    r"\blooking for (a )?position\b",
    r"\blooking for (new )?projects?\b",
    r"\bavailable for (hire|work|projects)\b",
    r"\bmy (portfolio|resume|cv|rate)\b",
    r"\byears? of experience\b",
    r"\bя\s+(?:\w+\s+){0,3}(работаю|разработчик|программист|дизайнер|фрилансер|специалист)\b",
]

# Спам и скам. Хештег #реклама и типичные рекламные посты отсекаем сразу.
SPAM_STOP_PATTERNS: list[str] = [
    # Финансы, схемы, скам
    r"\bказино\b",
    r"\bcasino\b",
    r"\bкриптовалют\w*",
    r"\bинвестиц\w*",
    r"\bпромокод\b",
    r"\bвывод денег\b",
    r"\bслив\b",
    r"\bпассивн\w*\s+заработок\b",
    r"\bзаработок\s+(от|без|на дому)\b",
    r"\bторговые сигналы\b",
    # Обучение и курсы
    r"\bзаписывай\w*\s+на\s+курс",
    r"\bбесплатн\w+\s+курс",
    r"\bкурс(ы)?\s+(с нуля|для начинающ\w*)",
    r"\bскидк\w*\s+на\s+курс",
    r"\bвебинар\w*",
    r"\bинтенсив\w*",
    r"\bнаставничеств\w*",
    r"\botus\.ru\b",
    r"\bоткрыт\w*\s+урок\b",
    r"\bоткрыт\w*\s+вебинар\w*",
    # Реклама: хештеги, маркировка и трекинг
    r"#реклам\w*",
    r"#ad\b",
    r"#ads\b",
    r"#advert\w*",
    r"реклама\.",
    r"(?m)^[\s*_]*реклама\b",
    r"\berid=",
    r"\butm_(?:source|medium|campaign|content|term)=",
    r"\bогрн\b",
    r"\bclck\.ru\b",
    r"\bреклам\w*\s+(?:место|пост|интеграц)\w*",
    r"\bкупить\s+рекламу\b",
    r"\bзаказать\s+рекламу\b",
    # Раскрутка каналов
    r"\bподписывай(тесь|ся)\b",
    r"\bпереходи(?:те)?\s+по\s+ссылке\b",
    r"\bнаш\s+канал\b",
    r"\bвход\s+по\s+ссылке\b",
    r"\bпартн[её]рск\w*\s+программ\w*",
    r"\bвзаимн\w*\s+пиар\b",
    r"\bpr[- ]?менеджер\b",
]

# Группа 1: интент найма / заказа
ACTION_KEYWORDS: list[str] = [
    r"\bищ(у|ем)\b",
    r"\bнуж(ен|на|ны)\b",
    r"\bтребу[ею]тся\b",
    r"\bприглаша(ем|ется|ются)\b",
    r"\bваканси[яи]\b",
    r"\bзаказ\b",
    r"\bтз\b",
    r"\bтехническое задание\b",
    r"\bна проект\b",
    r"\bhiring\b",
    r"\blooking for\b",
    r"\bneed(?:ed)?\b",
]

# Группа 2: роли, артефакты и технологии
ROLE_KEYWORDS: list[str] = [
    r"\bразработчик\w*",
    r"\bпрограммист\w*",
    r"\bдизайнер\w*",
    r"\bверстальщик\w*",
    r"\bкопирайтер\w*",
    r"\bмонтаж[её]р\w*",
    r"\bвидеомонтаж\w*",
    r"\bподрядчик\w*",
    r"\bфрилансер\w*",
    r"\bdeveloper\b",
    r"\bdesigner\b",
    r"\bfrontend\b",
    r"\bbackend\b",
    r"\bfullstack\b",
    r"\bpython\b",
    r"(?<!\w)(?:c\+\+|c#)(?!\w)",
    r"\b(?:golang|rust|php|java)\b",
    r"\b(?:react|vue|node(?:\.js)?|fastapi|django)\b",
    r"\b(?:бот|ботов|бота)\b",
    r"\b(?:парсер|парсинг)\b",
    r"\bскрипт\b",
    r"\bлендинг\w*",
    r"\bсайт(?:а|у|ом|ы|ов)?\b",
    r"\bприложени[еяю]\b",
    r"\bинтернет[- ]?магазин\w*",
]

# Группа 3: слова про оплату. Конкретные суммы вытаскивает collector.extract.
PAYMENT_PATTERNS: list[str] = [
    r"\bбюджет\b",
    r"\bоплат[аеуы]\b",
    r"\bзарплат[аеуы]\b",
    r"\bставка\b",
    r"\bbudget\b",
]


def _compile(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


RESUME_STOP_RE = _compile(RESUME_STOP_PATTERNS)
SPAM_STOP_RE = _compile(SPAM_STOP_PATTERNS)
ACTION_RE = _compile(ACTION_KEYWORDS)
ROLE_RE = _compile(ROLE_KEYWORDS)
PAYMENT_RE = _compile(PAYMENT_PATTERNS)


# ---------------------------------------------------------------------------
# Каталог категорий для пользовательских фильтров (inline-меню).
# key  — уникальный slug, хранится в БД через запятую.
# label — отображаемое название кнопки.
# match — подстроки / слова, по которым категория матчится в тексте заказа.
# ---------------------------------------------------------------------------
FILTER_CATEGORIES: list[dict[str, str | list[str]]] = [
    {"key": "web",        "label": "🌐 Веб-разработка",     "match": ["сайт", "лендинг", "верстка", "frontend", "backend", "fullstack", "html", "css", "web"]},
    {"key": "mobile",     "label": "📱 Мобильные приложения","match": ["приложение", "ios", "android", "flutter", "react native", "swift", "kotlin", "мобильн"]},
    {"key": "bot",        "label": "🤖 Боты и автоматизация","match": ["бот", "бота", "ботов", "телеграм", "telegram", "автоматизац", "парсер", "парсинг", "скрипт"]},
    {"key": "design",     "label": "🎨 Дизайн",             "match": ["дизайн", "дизайнер", "figma", "ui", "ux", "логотип", "баннер", "макет"]},
    {"key": "copywrite",  "label": "✍️ Копирайтинг",        "match": ["копирайт", "текст", "статья", "рерайт", "seo", "контент"]},
    {"key": "video",      "label": "🎬 Видеомонтаж",        "match": ["видеомонтаж", "монтаж", "монтажер", "монтажёр", "видео", "анимац", "motion"]},
    {"key": "backend",    "label": "⚙️ Backend / API",      "match": ["python", "django", "fastapi", "node", "golang", "rust", "php", "java", "api", "сервер", "backend"]},
    {"key": "ecommerce",  "label": "🛒 Интернет-магазины",  "match": ["магазин", "ecommerce", "e-commerce", "shopify", "woocommerce", "opencart", "1с-битрикс", "битрикс"]},
    {"key": "data",       "label": "📊 Данные и аналитика",  "match": ["аналитик", "данных", "data", "ml", "machine learning", "нейросет", "excel", "power bi", "tableau"]},
    {"key": "devops",     "label": "☁️ DevOps / Серверы",    "match": ["devops", "docker", "kubernetes", "linux", "сервер", "хостинг", "vps", "aws", "ci/cd"]},
]

# Фильтры по стеку / языкам. key начинается с stk_, чтобы не пересекаться с категориями.
FILTER_STACKS: list[dict[str, str | list[str]]] = [
    {"key": "stk_python",     "label": "🐍 Python",      "match": ["python", "django", "fastapi", "flask"]},
    {"key": "stk_js",         "label": "🟨 JavaScript",  "match": ["javascript", "js", "node", "nodejs", "node.js"]},
    {"key": "stk_ts",         "label": "🔷 TypeScript",  "match": ["typescript", "ts"]},
    {"key": "stk_react",      "label": "⚛️ React",       "match": ["react", "next.js", "nextjs"]},
    {"key": "stk_vue",        "label": "💚 Vue",         "match": ["vue", "nuxt"]},
    {"key": "stk_php",        "label": "🐘 PHP",         "match": ["php", "laravel", "wordpress", "bitrix", "битрикс"]},
    {"key": "stk_java",       "label": "☕ Java",        "match": ["java", "spring", "kotlin"]},
    {"key": "stk_csharp",     "label": "💠 C# / .NET",   "match": ["c#", ".net", "asp.net", "dotnet"]},
    {"key": "stk_go",         "label": "🔵 Go",          "match": ["golang", "go lang"]},
    {"key": "stk_rust",       "label": "🦀 Rust",        "match": ["rust"]},
    {"key": "stk_mobile",     "label": "📱 Flutter/RN",  "match": ["flutter", "react native", "swift", "kotlin", "ios", "android"]},
    {"key": "stk_devops",     "label": "🐳 DevOps",      "match": ["docker", "kubernetes", "devops", "ci/cd", "terraform"]},
]

CATEGORY_KEYS = {cat["key"] for cat in FILTER_CATEGORIES}
STACK_KEYS = {stack["key"] for stack in FILTER_STACKS}
