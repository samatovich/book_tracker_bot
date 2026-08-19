import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiohttp import web
import database as db
from handlers import router

BOT_TOKEN = "8902617824:AAFYW3P5sw_vYPpZRV2FcIfZCEKVw6HKmck"

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Ботту баштоо"),
        BotCommand(command="pin", description="Топко кошулуу (ПИН-код аркылуу)"),
        BotCommand(command="make_admin", description="Жаңы топ түзүү"),
        BotCommand(command="admin", description="Статистиканы Excelде жүктөө"),
        BotCommand(command="rename", description="Категория атын өзгөртүү"),
        BotCommand(command="cancel", description="Процессти жокко чыгаруу"),
    ]
    await bot.set_my_commands(commands)

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    
    await db.init_db()
    
    # Render'дин Web Service акысыз тарифи үчүн портту иштетебиз
    await start_web_server()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await set_bot_commands(bot)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
