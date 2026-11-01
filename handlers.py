"""Обработчики сообщений и кнопок.

Порядок регистрации важен: aiogram проверяет обработчики сверху вниз.
1. Команды и отмена — работают из любого состояния.
2. Кнопки главного меню.
3. Шаги заявки (FSM).
4. «Запасные» обработчики для неверного ввода и устаревших кнопок.
"""

import html
import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, User

import keyboards as kb
from config import Config
from states import OrderForm

router = Router()
logger = logging.getLogger(__name__)

TOTAL_STEPS = 7

# ---------------------------------------------------------------------------
# Тексты. Цены и контакты — демонстрационные, их нужно заменить на реальные.
# ---------------------------------------------------------------------------

WELCOME_TEXT = (
    "Здравствуйте{name}! 👋\n\n"
    "Я бот клининговой компании. Помогу оставить заявку на уборку — "
    "это займёт около минуты.\n\n"
    "Выберите нужный пункт меню 👇"
)

SERVICES_TEXT = (
    "<b>💰 Услуги и цены</b>\n"
    "<i>Цены указаны для примера (демо-версия бота).</i>\n\n"
    "🧽 <b>Поддерживающая уборка</b> — от 80 ₽/м²\n"
    "Пыль, полы, сантехника, кухонные поверхности.\n\n"
    "✨ <b>Генеральная уборка</b> — от 150 ₽/м²\n"
    "Всё помещение, включая труднодоступные места.\n\n"
    "🏗 <b>Уборка после ремонта</b> — от 200 ₽/м²\n"
    "Строительная пыль, следы краски и затирки.\n\n"
    "🪟 <b>Мытьё окон</b> — от 400 ₽ за створку\n\n"
    "Точную стоимость менеджер рассчитает после заявки."
)

CONTACTS_TEXT = (
    "<b>📞 Контакты</b>\n"
    "<i>Демонстрационные данные.</i>\n\n"
    "Телефон: +7 (000) 000-00-00\n"
    "Email: info@example.com\n"
    "Режим работы: ежедневно 8:00–21:00\n\n"
    "Самый быстрый способ — оставить заявку прямо в этом боте."
)

HELP_TEXT = (
    "<b>❓ Помощь</b>\n\n"
    "• Нажмите «📝 Оставить заявку» и ответьте на 7 вопросов.\n"
    "• В конце проверьте данные и нажмите «✅ Подтвердить».\n"
    "• Прервать заполнение можно в любой момент кнопкой «❌ Отменить» "
    "или командой /cancel.\n\n"
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/order — оставить заявку\n"
    "/cancel — отменить заполнение\n"
    "/help — эта справка"
)

# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------

# Телефон: цифры, пробелы, дефисы, скобки и необязательный «+» в начале.
PHONE_RE = re.compile(r"^\+?[\d\s\-()]+$")
# Username в Telegram: 5–32 символа, латиница, цифры и «_», начинается с буквы.
USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{4,31})$")
TG_LINK_RE = re.compile(r"^(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/?$")


def validate_name(text: str) -> str | None:
    """Имя: 2–50 символов, хотя бы одна буква."""
    name = " ".join(text.split())  # убираем лишние пробелы
    if not 2 <= len(name) <= 50:
        return None
    if not any(ch.isalpha() for ch in name):
        return None
    return name


def validate_contact(text: str) -> str | None:
    """Принимает телефон (10–15 цифр), @username или ссылку t.me/username."""
    value = text.strip()

    if match := TG_LINK_RE.match(value):
        return f"@{match.group(1)}"

    if PHONE_RE.match(value):
        digits = re.sub(r"\D", "", value)
        if 10 <= len(digits) <= 15:
            return value
        return None

    if match := USERNAME_RE.match(value):
        return f"@{match.group(1)}"

    return None


def parse_area(text: str) -> float | None:
    """Площадь: положительное число до 10 000 м². Допускаются «45,5» и «60 м2»."""
    value = text.lower().replace(",", ".")
    value = re.sub(r"\s*(кв\.?\s*м\.?|м2|м²|m2|метр\w*)\s*$", "", value).strip()
    try:
        area = float(value)
    except ValueError:
        return None
    if not 0 < area <= 10_000:
        return None
    return round(area, 1)


def validate_free_text(text: str, min_len: int, max_len: int) -> str | None:
    value = text.strip()
    if min_len <= len(value) <= max_len:
        return value
    return None


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def step(n: int, question: str) -> str:
    return f"<b>Шаг {n} из {TOTAL_STEPS}.</b> {question}"


def format_order(data: dict) -> str:
    """Текст заявки. Все пользовательские данные экранируются для HTML."""
    e = html.escape
    area = data.get("area")
    area_text = f"{area:g} м²" if area is not None else "—"
    return (
        f"👤 <b>Имя:</b> {e(data.get('name', '—'))}\n"
        f"📞 <b>Контакт:</b> {e(data.get('contact', '—'))}\n"
        f"🧹 <b>Тип уборки:</b> {e(data.get('cleaning_type', '—'))}\n"
        f"📐 <b>Площадь:</b> {area_text}\n"
        f"📍 <b>Адрес/район:</b> {e(data.get('address', '—'))}\n"
        f"🗓 <b>Дата и время:</b> {e(data.get('date_time', '—'))}\n"
        f"💬 <b>Комментарий:</b> {e(data.get('comment') or 'нет')}"
    )


def format_admin_message(data: dict, user: User) -> str:
    username = f"@{user.username}" if user.username else "нет username"
    author = f'<a href="tg://user?id={user.id}">{html.escape(user.full_name)}</a>'
    return (
        "🆕 <b>Новая заявка на уборку</b>\n\n"
        f"{format_order(data)}\n\n"
        f"<b>Отправитель:</b> {author} ({html.escape(username)}, ID <code>{user.id}</code>)\n"
        f"<b>Создана:</b> {datetime.now():%d.%m.%Y %H:%M}"
    )


async def safe_edit_text(message: Message | None, text: str) -> None:
    """Редактирует сообщение бота; не падает, если сообщение слишком старое или удалено."""
    if not isinstance(message, Message):
        return
    try:
        await message.edit_text(text)
    except TelegramBadRequest as error:
        logger.debug("Не удалось отредактировать сообщение: %s", error)


async def show_main_menu(message: Message, text: str = "Главное меню 👇") -> None:
    await message.answer(text, reply_markup=kb.main_menu())


async def begin_order(message: Message, state: FSMContext) -> None:
    """Начинает заполнение заявки с первого шага, сбрасывая старые данные."""
    await state.clear()
    await state.set_state(OrderForm.name)
    await message.answer(
        step(1, "Как к вам обращаться?"),
        reply_markup=kb.cancel_kb("Ваше имя"),
    )


async def ask_summary(message: Message, state: FSMContext) -> None:
    """Показывает итоговую заявку с кнопками подтверждения."""
    data = await state.get_data()
    await state.set_state(OrderForm.confirm)
    await message.answer("Почти готово! 🙌", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        f"<b>Проверьте заявку:</b>\n\n{format_order(data)}\n\nВсё верно?",
        reply_markup=kb.confirm_kb(),
    )


# ---------------------------------------------------------------------------
# 1. Команды и отмена (работают в любом состоянии)
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    first_name = message.from_user.first_name if message.from_user else ""
    name_part = f", {html.escape(first_name)}" if first_name else ""
    await show_main_menu(message, WELCOME_TEXT.format(name=name_part))


@router.message(Command("cancel"))
@router.message(F.text == kb.BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await show_main_menu(message, "Сейчас нечего отменять.")
        return
    await state.clear()
    await message.answer("Заполнение заявки отменено.", reply_markup=kb.main_menu())
    await message.answer("Что сделаем дальше?", reply_markup=kb.after_cancel_kb())


# ---------------------------------------------------------------------------
# 2. Главное меню
# ---------------------------------------------------------------------------


@router.message(Command("order"))
@router.message(F.text == kb.BTN_ORDER)
async def menu_order(message: Message, state: FSMContext) -> None:
    await begin_order(message, state)


@router.message(F.text == kb.BTN_SERVICES)
async def menu_services(message: Message) -> None:
    await message.answer(SERVICES_TEXT)


@router.message(F.text == kb.BTN_CONTACTS)
async def menu_contacts(message: Message) -> None:
    await message.answer(CONTACTS_TEXT)


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def menu_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(F.data == kb.CB_RESTART)
async def nav_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await safe_edit_text(callback.message, "Начинаем заново 🔄")
    await begin_order(callback.message, state)


@router.callback_query(F.data == kb.CB_MENU)
async def nav_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, "Возвращаемся в главное меню 🏠")
    await show_main_menu(callback.message)


# ---------------------------------------------------------------------------
# 3. Шаги заявки
# ---------------------------------------------------------------------------


@router.message(OrderForm.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    name = validate_name(message.text)
    if name is None:
        await message.answer(
            "Имя должно содержать от 2 до 50 символов и хотя бы одну букву. "
            "Попробуйте ещё раз 🙂"
        )
        return

    await state.update_data(name=name)
    await state.set_state(OrderForm.contact)
    await message.answer(
        step(
            2,
            f"Приятно познакомиться, {html.escape(name)}!\n\n"
            "Как с вами связаться? Нажмите «📱 Отправить мой номер» "
            "или напишите телефон либо Telegram-username (например, @username).",
        ),
        reply_markup=kb.contact_kb(),
    )


async def save_contact_and_continue(message: Message, state: FSMContext, contact: str) -> None:
    await state.update_data(contact=contact)
    await state.set_state(OrderForm.cleaning_type)
    # Сначала меняем нижнюю клавиатуру, затем показываем inline-кнопки:
    # у одного сообщения не может быть обоих типов клавиатуры.
    await message.answer("Контакт сохранён ✅", reply_markup=kb.cancel_kb("Выберите кнопку выше"))
    await message.answer(step(3, "Выберите тип уборки:"), reply_markup=kb.cleaning_types_kb())


@router.message(OrderForm.contact, F.contact)
async def process_contact_shared(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await save_contact_and_continue(message, state, phone)


@router.message(OrderForm.contact, F.text)
async def process_contact_text(message: Message, state: FSMContext) -> None:
    contact = validate_contact(message.text)
    if contact is None:
        await message.answer(
            "Не похоже на телефон или Telegram-контакт 🤔\n\n"
            "Примеры: <code>+7 900 123-45-67</code>, <code>89001234567</code>, "
            "<code>@username</code>.\nИли нажмите «📱 Отправить мой номер»."
        )
        return
    await save_contact_and_continue(message, state, contact)


@router.callback_query(OrderForm.cleaning_type, F.data.startswith(kb.CB_TYPE_PREFIX))
async def process_cleaning_type(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.removeprefix(kb.CB_TYPE_PREFIX)
    label = kb.CLEANING_TYPES.get(key)
    if label is None:
        await callback.answer("Неизвестный вариант, выберите из списка.", show_alert=True)
        return

    await state.update_data(cleaning_type=label)
    await state.set_state(OrderForm.area)
    await callback.answer()
    # Убираем кнопки, чтобы тип нельзя было «перевыбрать» старым сообщением.
    await safe_edit_text(callback.message, step(3, f"Тип уборки: <b>{label}</b> ✅"))

    extra = "\n\nДетали задачи вы сможете описать в комментарии." if key == "other" else ""
    await callback.message.answer(
        step(4, f"Укажите площадь помещения в м² (например, 45 или 62,5).{extra}"),
        reply_markup=kb.cancel_kb("Площадь в м²"),
    )


@router.message(OrderForm.cleaning_type)
async def cleaning_type_wrong_input(message: Message) -> None:
    await message.answer(
        "Пожалуйста, выберите тип уборки кнопкой 👇",
        reply_markup=kb.cleaning_types_kb(),
    )


@router.message(OrderForm.area, F.text)
async def process_area(message: Message, state: FSMContext) -> None:
    area = parse_area(message.text)
    if area is None:
        await message.answer(
            "Площадь должна быть положительным числом (не больше 10 000 м²). "
            "Например: <code>45</code> или <code>62,5</code>."
        )
        return

    await state.update_data(area=area)
    await state.set_state(OrderForm.address)
    await message.answer(
        step(5, "Укажите район или адрес, куда нужно приехать."),
        reply_markup=kb.cancel_kb("Район или адрес"),
    )


@router.message(OrderForm.address, F.text)
async def process_address(message: Message, state: FSMContext) -> None:
    address = validate_free_text(message.text, min_len=3, max_len=200)
    if address is None:
        await message.answer("Адрес должен содержать от 3 до 200 символов. Попробуйте ещё раз.")
        return

    await state.update_data(address=address)
    await state.set_state(OrderForm.date_time)
    await message.answer(
        step(6, "Когда вам удобно? Напишите желаемую дату и время.\n"
                "Например: <i>15 ноября, после 10:00</i> или <i>в эту субботу утром</i>."),
        reply_markup=kb.cancel_kb("Дата и время"),
    )


@router.message(OrderForm.date_time, F.text)
async def process_date_time(message: Message, state: FSMContext) -> None:
    date_time = validate_free_text(message.text, min_len=2, max_len=100)
    if date_time is None:
        await message.answer("Укажите дату и время короче — до 100 символов.")
        return

    await state.update_data(date_time=date_time)
    await state.set_state(OrderForm.comment)
    await message.answer(
        step(7, "Добавьте комментарий: есть ли животные, особые пожелания, "
                "нужен ли свой инвентарь и т. п.\nЕсли нечего добавить — нажмите «Пропустить»."),
        reply_markup=kb.comment_kb(),
    )


@router.message(OrderForm.comment, F.text == kb.BTN_SKIP)
async def process_comment_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(comment=None)
    await ask_summary(message, state)


@router.message(OrderForm.comment, F.text)
async def process_comment(message: Message, state: FSMContext) -> None:
    comment = validate_free_text(message.text, min_len=1, max_len=500)
    if comment is None:
        await message.answer("Комментарий слишком длинный — максимум 500 символов.")
        return
    await state.update_data(comment=comment)
    await ask_summary(message, state)


@router.callback_query(OrderForm.confirm, F.data == kb.CB_CONFIRM)
async def process_confirm(
    callback: CallbackQuery, state: FSMContext, bot: Bot, config: Config
) -> None:
    data = await state.get_data()

    try:
        await bot.send_message(config.admin_id, format_admin_message(data, callback.from_user))
    except TelegramAPIError:
        logger.exception("Не удалось отправить заявку администратору %s", config.admin_id)
        # Состояние не сбрасываем — пользователь может нажать «Подтвердить» ещё раз.
        await callback.answer(
            "Не удалось отправить заявку. Попробуйте ещё раз через минуту "
            "или свяжитесь с нами по контактам из меню.",
            show_alert=True,
        )
        return

    await state.clear()
    await callback.answer("Заявка отправлена!")
    await safe_edit_text(
        callback.message, f"<b>Ваша заявка:</b>\n\n{format_order(data)}\n\n✅ <b>Отправлена</b>"
    )
    await show_main_menu(
        callback.message,
        "Спасибо! Заявка принята 🎉\nМенеджер свяжется с вами в ближайшее время.",
    )


@router.callback_query(OrderForm.confirm, F.data == kb.CB_DECLINE)
async def process_decline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Заявка отменена")
    await safe_edit_text(callback.message, "❌ Заявка отменена и не была отправлена.")
    await callback.message.answer("Что сделаем дальше?", reply_markup=kb.after_cancel_kb())


@router.message(OrderForm.confirm)
async def confirm_wrong_input(message: Message) -> None:
    await message.answer(
        "Пожалуйста, нажмите «✅ Подтвердить» или «❌ Отменить» под заявкой 👆",
        reply_markup=kb.confirm_kb(),
    )


# ---------------------------------------------------------------------------
# 4. Запасные обработчики
# ---------------------------------------------------------------------------


@router.message(OrderForm.contact)
async def contact_wrong_type(message: Message) -> None:
    await message.answer(
        "Отправьте телефон или @username текстом, либо нажмите «📱 Отправить мой номер»."
    )


@router.message(
    StateFilter(
        OrderForm.name, OrderForm.area, OrderForm.address, OrderForm.date_time, OrderForm.comment
    )
)
async def form_wrong_type(message: Message) -> None:
    """Пользователь прислал фото, стикер, голосовое и т. п. вместо текста."""
    await message.answer("Пожалуйста, ответьте текстовым сообщением ✍️")


@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    """Нажатие на кнопку из старого сообщения (например, после отмены заявки)."""
    await callback.answer(
        "Эта кнопка уже неактивна. Начните заново через главное меню.",
        show_alert=True,
    )


@router.message()
async def unknown_message(message: Message) -> None:
    await show_main_menu(message, "Я не понял сообщение 🙂 Выберите пункт меню ниже.")
