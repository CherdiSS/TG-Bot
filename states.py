"""Состояния FSM для пошагового заполнения заявки."""

from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    name = State()           # Шаг 1: имя
    contact = State()        # Шаг 2: телефон или Telegram-контакт
    cleaning_type = State()  # Шаг 3: тип уборки (inline-кнопки)
    area = State()           # Шаг 4: площадь, м²
    address = State()        # Шаг 5: район или адрес
    date_time = State()      # Шаг 6: желаемая дата и время
    comment = State()        # Шаг 7: комментарий
    confirm = State()        # Проверка и подтверждение заявки
