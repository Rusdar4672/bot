import hashlib
import re


def order_fingerprint(text: str) -> str:
    """Хеш текста заказа для дедупа между каналами."""
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"@\w+", " ", normalized)
    normalized = re.sub(r"#\w+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    # Берём устойчивое ядро, чтобы мелкие правки даты/контактов не плодили дубли
    core = normalized[:1200]
    return hashlib.sha256(core.encode("utf-8")).hexdigest()
