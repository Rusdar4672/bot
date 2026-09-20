import re
from dataclasses import dataclass, field

from collector.extract import Contacts, extract_amounts, extract_contacts, extract_job_meta
from collector.filters import (
    ACTION_RE,
    CHAT_NOISE_RE,
    MODERATION_AUTHOR_RE,
    MODERATION_STOP_RE,
    PAYMENT_RE,
    RESUME_STOP_RE,
    ROLE_RE,
    SPAM_STOP_RE,
)

MIN_TEXT_LENGTH = 25
# Короткие сообщения без оплаты/контактов почти всегда трёп, а не вакансия
MIN_ORDER_LENGTH = 60

# Дополнительные сигналы резюме (не стоп сами по себе, но в сумме режут пост)
RESUME_SOFT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\bопыт\s+\d+",
        r"\b\d+\+?\s*год",
        r"\bстаж\b",
        r"\bпортфолио\b",
        r"\bставк[аи]\b",
        r"\bчас\b",
        r"\b/час\b",
        r"\bв час\b",
        r"\bhourly\b",
        r"\bper hour\b",
        r"\bтехнологическ\w*\s+стек\b",
        r"\bпроекты и опыт\b",
        r"\bпиши(те)?\s+в\s+(лс|личку|телеграм)\b",
        r"(?m)^л[сc]\s*:",
        r"\bв личке\b",
        r"\bdm me\b",
        r"\bcontact me\b",
        r"github\.io",
        r"\bмоя команда\b",
        r"\bнаша команда\b",
        r"\bпод ключ\b",
        r"\bберу\b",
    )
)

# «Если нужен разработчик — пишите» — не интент найма, а самопиар
EMPLOYER_ACTION_RE = re.compile(
    r"\b(ищем|требуется|требуются|приглашаем|вакансия|hiring|looking for)\b"
    r"|(?<!если )(?<!когда )(?<!нужен ли )(?<!нужна ли )\bнуж(ен|на|ны)\b"
)


@dataclass
class ParsedMessage:
    is_order: bool
    matched_keywords: list[str]
    text: str
    amounts: list[str] = field(default_factory=list)
    contacts: Contacts = field(default_factory=Contacts)
    job_type: str | None = None
    position: str | None = None
    languages: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _collect_matches(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        token = match.group(0).strip()
        if token and token not in seen:
            seen.add(token)
            found.append(token)
    return found


def _match_extra_keywords(text: str, extra_keywords: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw in extra_keywords:
        keyword = _normalize(raw).strip()
        if not keyword:
            continue
        if re.search(rf"\b{re.escape(keyword)}\b", text) and keyword not in seen:
            seen.add(keyword)
            found.append(raw.strip())
    return found


def _looks_like_resume(normalized: str) -> bool:
    """Жёсткие стоп-фразы или набор мягких сигналов без интента найма."""
    for pattern in RESUME_STOP_RE:
        if pattern.search(normalized):
            return True

    soft_hits = sum(1 for pattern in RESUME_SOFT_PATTERNS if pattern.search(normalized))
    has_employer_intent = bool(EMPLOYER_ACTION_RE.search(normalized))

    # Много «я специалист / ставка / портфолио», но нет «ищем/нужен»
    if soft_hits >= 3 and not has_employer_intent:
        return True
    if soft_hits >= 2 and re.search(r"\bя\b", normalized) and not has_employer_intent:
        return True
    return False


def is_junk_content(text: str, author: str | None = None) -> bool:
    """True для резюме, рекламы, модерации, чат-трёпа и прочего мусора."""
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return True
    if author and MODERATION_AUTHOR_RE.search(author.lstrip("@")):
        return True
    normalized = _normalize(text)
    for pattern in SPAM_STOP_RE:
        if pattern.search(normalized):
            return True
    for pattern in MODERATION_STOP_RE:
        if pattern.search(normalized):
            return True
    for pattern in CHAT_NOISE_RE:
        if pattern.search(normalized):
            return True
    return _looks_like_resume(normalized)


def parse_message(text: str, extra_keywords: list[str] | None = None) -> ParsedMessage:
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return ParsedMessage(is_order=False, matched_keywords=[], text=text)

    if is_junk_content(text):
        return ParsedMessage(is_order=False, matched_keywords=[], text=text)

    normalized = _normalize(text)

    action = _collect_matches(ACTION_RE, normalized)
    role = _collect_matches(ROLE_RE, normalized)
    payment = _collect_matches(PAYMENT_RE, normalized)
    extra = _match_extra_keywords(normalized, extra_keywords) if extra_keywords else []
    amounts = extract_amounts(text)
    contacts = extract_contacts(text)
    meta = extract_job_meta(text)

    has_payment = bool(payment) or bool(amounts)
    has_contact = bool(contacts.all())
    is_short = len(text.strip()) < MIN_ORDER_LENGTH

    # Короткие фразы без оплаты/контакта — не заказ (даже если «нужен сайт»)
    if is_short and not has_payment and not has_contact:
        is_order = False
    else:
        is_order = bool(action) and (bool(role) or has_payment or bool(extra))

    matched = list(dict.fromkeys(action + role + payment + extra))

    return ParsedMessage(
        is_order=is_order,
        matched_keywords=matched,
        text=text,
        amounts=amounts,
        contacts=contacts,
        job_type=meta.job_type,
        position=meta.position,
        languages=meta.languages,
        hashtags=meta.hashtags,
    )
