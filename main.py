"""Точка входу: веб-сервер магазину + Telegram-бот в одному процесі."""
import asyncio
import logging

from aiohttp import web

import db
from config import ADMIN_CHAT_ID, BOT_TOKEN, WEB_HOST, WEB_PORT
from web import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


async def wait_for_telegram(bot) -> None:
    """Перевіряє токен; якщо Telegram просить зачекати (flood control) — чекає."""
    from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

    while True:
        try:
            me = await bot.get_me()
            log.info("Бот підключений: @%s", me.username)
            return
        except TelegramRetryAfter as e:
            log.warning("Telegram просить зачекати %s с", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
        except TelegramNetworkError:
            log.warning("Немає зв'язку з Telegram — повтор через 15 с (сайт працює далі)")
            await asyncio.sleep(15)


async def setup_commands(bot) -> None:
    from aiogram.types import BotCommand, BotCommandScopeChat

    try:
        await bot.set_my_commands([BotCommand(command="status", description="Статус замовлення")])
        if ADMIN_CHAT_ID:
            await bot.set_my_commands(
                [
                    BotCommand(command="orders", description="Останні замовлення"),
                    BotCommand(command="stats", description="Виручка та статистика"),
                    BotCommand(command="status", description="Статус замовлення"),
                ],
                scope=BotCommandScopeChat(chat_id=ADMIN_CHAT_ID),
            )
    except Exception:
        log.exception("Не вдалося встановити команди")


async def run_bot(dp, bot) -> None:
    await wait_for_telegram(bot)
    await setup_commands(bot)
    await dp.start_polling(bot)


async def main() -> None:
    db.connect()
    bot = dp = None
    if BOT_TOKEN:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        from bot import router

        bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(router)
    else:
        log.warning("BOT_TOKEN не задано — працює лише сайт і адмінка")

    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, WEB_HOST, WEB_PORT).start()
    log.info("Магазин: http://%s:%s/  ·  Адмінка: http://%s:%s/admin", WEB_HOST, WEB_PORT, WEB_HOST, WEB_PORT)
    try:
        if dp is not None:
            await run_bot(dp, bot)
        else:
            await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        if bot is not None:
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
