"""Точка входа: настройка и запуск Telegram-бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from config import load_config
from handlers import router

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    """Глобальный обработчик непредвиденных ошибок: логируем, бот продолжает работу."""
    logger.exception("Необработанная ошибка: %s", event.exception, exc_info=event.exception)

    message = event.update.message or (
        event.update.callback_query.message if event.update.callback_query else None
    )
    if message is not None:
        try:
            await message.answer("Произошла ошибка 😔 Попробуйте ещё раз или нажмите /start.")
        except Exception:  # noqa: BLE001 — не даём ошибке в уведомлении уронить бота
            pass
    return True


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    config = load_config()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # MemoryStorage хранит состояния в памяти: для демо этого достаточно.
    # В продакшене лучше использовать RedisStorage, чтобы не терять диалоги при перезапуске.
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config  # будет передан в обработчики как аргумент `config`
    dp.include_router(router)
    dp.errors.register(on_error)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="order", description="Оставить заявку"),
            BotCommand(command="cancel", description="Отменить заполнение"),
            BotCommand(command="help", description="Помощь"),
        ]
    )
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запущен. Заявки будут приходить администратору с ID %s", config.admin_id)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
