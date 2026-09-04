from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Bot API — для взаимодействия с пользователями
    bot_token: str

    # Telethon — для чтения сообщений из чатов/каналов
    api_id: int
    api_hash: str
    phone: str = ""

    # База данных
    database_url: str = "sqlite+aiosqlite:///./data/frelansebot.db"

    # Администраторы бота (telegram user id через запятую)
    admin_ids: str = ""

    # Сколько последних сообщений проверять при старте в каждом чате
    # (без уведомлений — только чтобы наполнить базу на 1–2 недели)
    history_scan_limit: int = 40

    # При скане истории слать уведомления (по умолчанию нет)
    history_scan_notify: bool = False

    # Максимальный возраст поста для сохранения в базу
    max_order_age_days: int = 14

    # Свежие заказы для показа/пуша в первую очередь
    recent_order_days: int = 7

    # Если за recent_order_days мало совпадений — добираем до этого возраста
    fallback_order_days: int = 14

    @property
    def admin_id_list(self) -> list[int]:
        if not self.admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]


settings = Settings()
