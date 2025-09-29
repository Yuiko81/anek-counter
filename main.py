import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from bot.config import settings
from bot.database import Database
from bot.handlers import register_handlers


async def main() -> None:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    database = Database(dsn=settings.database_url)
    await database.connect()

    register_handlers(dp, database)

    try:
        await dp.start_polling(bot)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
