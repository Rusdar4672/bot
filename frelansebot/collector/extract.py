import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)

TG_AT_RE = re.compile(r"(?<![\w.])@([a-zA-Z][a-zA-Z0-9_]{4,31})\b")

TG_LINK_RE = re.compile(
    r"(?:https?://)?(?:t(?:elegram)?\.me|telegram\.dog)/"
    r"(?:joinchat/([A-Za-z0-9_-]+)|(\+[A-Za-z0-9_-]+)|@?([a-zA-Z][a-zA-Z0-9_]{4,31}))",
    re.IGNORECASE,
)

TG_RESERVED = {"joinchat", "addstickers", "proxy", "socks", "share", "iv"}

PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().\-]{8,20}\d)(?!\d)")

AMOUNT_RE = re.compile(
    r"""
    (?:
        (?:от\s+)?\d{1,3}(?:[\s\u00a0]\d{3})*\s*(?:к|тыс(?:яч|\.)?|руб(?:л(?:ей|я|ь))?|\$|€|₽)?\s+до\s+\d{1,3}(?:[\s\u00a0]\d{3})*\s*(?:к|тыс(?:яч|\.)?|руб(?:л(?:ей|я|ь))?|\$|€|₽|usd|usdt|eur|евро)
        |
        (?:от\s+)?(?:\$|€|₽)\s*\d{1,3}(?:[\s\u00a0]\d{3})+(?:[.,]\d+)?
        |
        (?:от\s+)?(?:\$|€|₽)\s*\d{2,9}(?:[.,]\d+)?
        |
        (?:от\s+)?\d{1,3}(?:[\s\u00a0]\d{3})+(?:[.,]\d+)?\s*(?:\$|€|₽|руб(?:л(?:ей|я|ь))?|rub|usd|usdt|eur|евро)
        |
        (?:от\s+)?(?<!\d)(?<!\d[\s\u00a0])\d{1,9}(?:[.,]\d+)?\s*(?:\$|€|₽|руб(?:л(?:ей|я|ь))?|rub|usd|usdt|eur|евро)
        |
        (?:от\s+)?(?<!\d)\d{1,5}\s*(?:к|тыс(?:яч|\.)?)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_AMOUNT_AFTER_PHONE = re.compile(r"^\s*(?:руб|usd|eur|usdt|€|\$|к\b|тыс)", re.IGNORECASE)


@dataclass
class Contacts:
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    telegrams: list[str] = field(default_factory=list)

    def all(self) -> list[str]:
        return [*self.telegrams, *self.phones, *self.emails]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _drop_contained(spans: list[tuple[int, int, str]]) -> list[str]:
    spans = sorted(spans, key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, value in spans:
        if any(start >= other[0] and end <= other[1] for other in kept):
            continue
        kept.append((start, end, value))
    kept.sort(key=lambda item: item[0])
    return [value for _, _, value in kept]


def extract_amounts(text: str) -> list[str]:
    spans = [
        (match.start(), match.end(), re.sub(r"\s+", " ", match.group(0)).strip())
        for match in AMOUNT_RE.finditer(text)
    ]
    return _drop_contained(spans)


def extract_contacts(text: str) -> Contacts:
    emails = _unique(EMAIL_RE.findall(text))
    masked = EMAIL_RE.sub(" ", text)

    telegrams: list[str] = []
    for match in TG_AT_RE.finditer(masked):
        telegrams.append(f"@{match.group(1)}")

    for match in TG_LINK_RE.finditer(masked):
        joinchat, invite, username = match.groups()
        if joinchat:
            telegrams.append(f"https://t.me/joinchat/{joinchat}")
        elif invite:
            telegrams.append(f"https://t.me/{invite}")
        elif username and username.lower() not in TG_RESERVED:
            telegrams.append(f"@{username}")

    phones: list[str] = []
    phone_keys: set[str] = set()
    for match in PHONE_RE.finditer(masked):
        raw = re.sub(r"\s+", " ", match.group(0)).strip()
        digits = re.sub(r"\D", "", raw)
        if not (10 <= len(digits) <= 15):
            continue
        tail = masked[match.end() : match.end() + 8]
        if _AMOUNT_AFTER_PHONE.match(tail):
            continue
        key = digits[-10:]
        if key in phone_keys:
            continue
        phone_keys.add(key)
        phones.append(raw)

    return Contacts(phones=phones, emails=emails, telegrams=_unique(telegrams))


# ---------------------------------------------------------------------------
# Языки, тип вакансии, позиция, хештеги
# ---------------------------------------------------------------------------

HASHTAG_RE = re.compile(r"(?<!\w)#([a-zA-Zа-яА-ЯёЁ0-9_]+)")

PROGRAMMING_LANGUAGES: list[tuple[str, str]] = [
    ("Python", r"\bpython\b"),
    ("JavaScript", r"\b(?:javascript|js)\b"),
    ("TypeScript", r"\btypescript\b|\bts\b"),
    ("Java", r"\bjava\b"),
    ("C#", r"\bc#\b"),
    ("C++", r"\bc\+\+\b"),
    ("Go", r"\bgolang\b|\bgo lang\b"),
    ("Rust", r"\brust\b"),
    ("PHP", r"\bphp\b"),
    ("Ruby", r"\bruby\b"),
    ("Swift", r"\bswift\b"),
    ("Kotlin", r"\bkotlin\b"),
    ("Dart", r"\bdart\b"),
    ("SQL", r"\bsql\b"),
    ("1C", r"\b1[сc]\b"),
]

FRAMEWORKS: list[tuple[str, str]] = [
    ("React", r"\breact\b"),
    ("Vue", r"\bvue\b"),
    ("Angular", r"\bangular\b"),
    ("Node.js", r"\bnode(?:\.js)?\b"),
    ("Django", r"\bdjango\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Flutter", r"\bflutter\b"),
    ("React Native", r"\breact native\b"),
    (".NET", r"\b\.net\b|\basp\.net\b"),
    ("Laravel", r"\blaravel\b"),
    ("Spring", r"\bspring\b"),
]

JOB_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("фриланс", [r"\bфриланс", r"\bfreelance\b", r"\bразов\w*\s+заказ", r"\bподряд", r"\bзаказ\b"]),
    ("вакансия", [r"\bваканси", r"\bв штат", r"\bfull[- ]?time\b", r"\bофисн\w*\s+работ", r"\bhiring\b"]),
    ("проект", [r"\bна проект\b", r"\bпроект\b", r"\bproject\b"]),
]

POSITION_RULES: list[tuple[str, list[str]]] = [
    ("Frontend", [r"\bfrontend\b", r"\bфронтенд", r"\bверстальщик", r"\bверстк"]),
    ("Backend", [r"\bbackend\b", r"\bбэкенд", r"\bбекенд", r"\bback-end\b"]),
    ("Fullstack", [r"\bfullstack\b", r"\bfull[- ]?stack\b", r"\bфулстек"]),
    ("Mobile", [r"\bmobile\b", r"\bмобильн", r"\bios\b", r"\bandroid\b", r"\bflutter\b"]),
    ("DevOps", [r"\bdevops\b", r"\bsre\b", r"\bkubernetes\b", r"\bdocker\b"]),
    ("QA", [r"\bqa\b", r"\bтестировщик", r"\bautotest\b", r"\bquality assurance\b"]),
    ("Data / ML", [r"\bdata scientist\b", r"\bml engineer\b", r"\bmachine learning\b", r"\bаналитик данных\b"]),
    ("Designer", [r"\bдизайнер\b", r"\bdesigner\b", r"\bui/ux\b", r"\bfigma\b"]),
    ("PM", [r"\bproduct manager\b", r"\bproject manager\b", r"\bпродакт\b", r"\bпроджект\b"]),
]

WORK_FORMAT_RULES: list[tuple[str, list[str]]] = [
    ("удалёнка", [r"\bудал[её]н", r"\bremote\b", r"\bдистанцион"]),
    ("офис", [r"\bв офис", r"\bофис\b", r"\bon[- ]?site\b"]),
    ("гибрид", [r"\bгибрид", r"\bhybrid\b"]),
]


@dataclass
class JobMeta:
    job_type: str | None = None
    position: str | None = None
    work_format: str | None = None
    languages: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)


def _first_match(normalized: str, rules: list[tuple[str, list[str]]]) -> str | None:
    for label, patterns in rules:
        for pattern in patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                return label
    return None


def _collect_labeled(normalized: str, catalog: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for label, pattern in catalog:
        if re.search(pattern, normalized, re.IGNORECASE) and label not in seen:
            seen.add(label)
            found.append(label)
    return found


def extract_job_meta(text: str) -> JobMeta:
    normalized = text.lower().replace("ё", "е")

    languages = _collect_labeled(normalized, PROGRAMMING_LANGUAGES)
    technologies = _collect_labeled(normalized, FRAMEWORKS)
    job_type = _first_match(normalized, JOB_TYPE_RULES)
    position = _first_match(normalized, POSITION_RULES)
    work_format = _first_match(normalized, WORK_FORMAT_RULES)

    hashtags: list[str] = []
    seen: set[str] = set()

    def add_tag(tag: str) -> None:
        clean = tag.strip().lower().replace(" ", "_")
        if clean and clean not in seen:
            seen.add(clean)
            hashtags.append(clean)

    for match in HASHTAG_RE.finditer(text):
        add_tag(match.group(1))

    if job_type:
        add_tag(job_type)
    if position:
        add_tag(position.replace(" / ", "_").replace(" ", "_").lower())
    if work_format:
        add_tag(work_format)
    for lang in languages:
        add_tag(lang)
    for tech in technologies:
        add_tag(tech.replace(".", "").replace(" ", "_").lower())

    return JobMeta(
        job_type=job_type,
        position=position,
        work_format=work_format,
        languages=languages,
        technologies=technologies,
        hashtags=hashtags,
    )

