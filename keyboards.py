"""Клавиатуры бота.

Reply-клавиатуры (под полем ввода) — для меню и служебных действий.
Inline-клавиатуры (под сообщением) — для выбора вариантов и подтверждения.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --- Тексты кнопок главного меню ---
BTN_ORDER = "📝 Оставить заявку"
BTN_SERVICES = "💰 Услуги и цены"
BTN_CONTACTS = "📞 Контакты"
BTN_HELP = "❓ Помощь"

# --- Служебные кнопки ---
BTN_CANCEL = "❌ Отменить"
BTN_SKIP = "➡️ Пропустить"
BTN_SHARE_PHONE = "📱 Отправить мой номер"

# Типы уборки: ключ для callback_data -> подпись на кнопке
CLEANING_TYPES: dict[str, str] = {
    "regular": "🧽 Поддерживающая уборка",
    "general": "✨ Генеральная уборка",
    "renovation": "🏗 Уборка после ремонта",
    "windows": "🪟 Мытьё окон",
    "other": "📋 Другое",
}

# callback_data для inline-кнопок
CB_TYPE_PREFIX = "type:"
CB_CONFIRM = "order:confirm"
CB_DECLINE = "order:decline"
CB_RESTART = "nav:restart"
CB_MENU = "nav:menu"


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню: 2 кнопки в ряд — удобно нажимать большим пальцем."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ORDER)],
            [KeyboardButton(text=BTN_SERVICES), KeyboardButton(text=BTN_CONTACTS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите пункт меню",
    )


def cancel_kb(placeholder: str = "Введите ответ") -> ReplyKeyboardMarkup:
    """Клавиатура с одной кнопкой отмены — показывается во время заполнения заявки."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder=placeholder,
    )


def contact_kb() -> ReplyKeyboardMarkup:
    """Шаг ввода контакта: можно отправить номер одной кнопкой или ввести вручную."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder="+7 900 123-45-67 или @username",
    )


def comment_kb() -> ReplyKeyboardMarkup:
    """Шаг комментария: комментарий необязателен, его можно пропустить."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SKIP)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Например: есть кошка, нужен пылесос",
    )


def cleaning_types_kb() -> InlineKeyboardMarkup:
    """Типы уборки — по одной кнопке в строке, чтобы длинный текст не обрезался."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"{CB_TYPE_PREFIX}{key}")]
            for key, label in CLEANING_TYPES.items()
        ]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=CB_CONFIRM)],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=CB_DECLINE)],
        ]
    )


def after_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data=CB_RESTART)],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_MENU)],
        ]
    )
