"""Чтение настроек бота из переменных окружения (или файла .env)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int


def load_config() -> Config:
    """Загружает настройки и проверяет, что они заданы корректно."""
    # Подхватываем .env, если он есть. Переменные окружения системы имеют приоритет.
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()

    if not bot_token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен от @BotFather."
        )

    if not admin_id_raw.lstrip("-").isdigit():
        raise RuntimeError(
            "ADMIN_ID не задан или не является числом. "
            "Укажите в .env свой числовой Telegram ID (например, 123456789)."
        )

    return Config(bot_token=bot_token, admin_id=int(admin_id_raw))
