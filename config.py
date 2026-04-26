import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            continue
    return ids


@dataclass(slots=True)
class Config:
    bot_token: str
    admin_ids: list[int]
    db_path: str
    rate_limit_seconds: float
    payment_mode: str
    crypto_pay_api_token: str
    crypto_pay_base_url: str
    welcome_sticker_id: str
    scheduler_tick_seconds: int


def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        db_path=os.getenv("DB_PATH", "bot.sqlite3"),
        rate_limit_seconds=float(os.getenv("RATE_LIMIT_SECONDS", "0.7")),
        payment_mode=os.getenv("PAYMENT_MODE", "simulate").strip().lower(),
        crypto_pay_api_token=os.getenv("CRYPTO_PAY_API_TOKEN", ""),
        crypto_pay_base_url=os.getenv("CRYPTO_PAY_BASE_URL", "https://pay.crypt.bot/api"),
        welcome_sticker_id=os.getenv("WELCOME_STICKER_ID", "").strip(),
        scheduler_tick_seconds=int(os.getenv("SCHEDULER_TICK_SECONDS", "15")),
    )


config = load_config()
