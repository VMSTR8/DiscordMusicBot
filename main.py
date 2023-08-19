import os

import asyncio

import logging

from datetime import datetime

import discord
from discord.ext import commands

import wavelink

from tortoise import run_async

from database.init import init

from cogs.music import MusicCog
from cogs.user_interaction import UserInteractionCog

from settings.settings import (
    BOT_TOKEN,
    WAVELINK_URI,
    WAVELINK_PASSWORD,
)

if not os.path.exists("logs"):
    os.makedirs("logs")

log_file_name = datetime.now().strftime("log_%Y_%m_%d_%H_%M.log")

bot_config = {
    'token': BOT_TOKEN,
    'prefix': '!',

}

intents = discord.Intents.all()
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=bot_config['prefix'],
    intents=intents,

)


async def connect_nodes() -> None:
    await bot.wait_until_ready()
    try:
        node: wavelink.Node = wavelink.Node(
            uri=WAVELINK_URI, password=WAVELINK_PASSWORD, secure=False)
        await wavelink.NodePool.connect(client=bot, nodes=[node])
    except Exception as error:
        logging.error(f"An error occurred while connecting nodes: {error}")


async def setup_bot(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot=bot))
    await bot.add_cog(UserInteractionCog(bot=bot))


def main() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(os.path.join("logs", log_file_name)),
            logging.StreamHandler()
        ]
    )

    # TODO сделать обработку ошибок конекта к бд
    run_async(init())

    @bot.event
    async def on_ready() -> None:
        logging.info(f'Logged in as {bot.user}')
        synced = await bot.tree.sync()
        await connect_nodes()
        try:
            logging.info(f"Synced {len(synced)} command(s)")
        except Exception as error:
            logging.error(f"An error occurred during syncing: {error}")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name='test'
        )
        await bot.change_presence(activity=activity)

    # TODO сделать правильное отсоединение при ctrl + c или разрыве, учесть и wavelink
    try:
        asyncio.run(setup_bot(bot=bot))
        bot.run(token=bot_config['token'])
    except Exception as error:
        logging.error(f"An error occurred while running the bot: {error}")


if __name__ == '__main__':
    main()
