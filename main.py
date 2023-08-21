import os

import asyncio

import aiohttp

import logging

from datetime import datetime

import discord
from discord.ext import commands

import wavelink

from tortoise import run_async, Tortoise

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
    '''
    Connects the bot to a wavelink node.
    '''
    await bot.wait_until_ready()
    try:
        node: wavelink.Node = wavelink.Node(
            uri=WAVELINK_URI,
            password=WAVELINK_PASSWORD,
            secure=False,
            retries=5
        )
        await wavelink.NodePool.connect(client=bot, nodes=[node])
    except aiohttp.client_exceptions.ClientConnectorError as error:
        logging.error(f"An error occurred while connecting nodes: {error}")
        await node._session.close()
        await bot.close()


async def setup_bot(bot: commands.Bot) -> None:
    '''
    Sets up cogs for the bot.
    '''
    await bot.add_cog(MusicCog(bot=bot))
    await bot.add_cog(UserInteractionCog(bot=bot))


def main() -> None:
    '''
    Main entry point of the bot.
    '''
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(os.path.join("logs", log_file_name)),
            logging.StreamHandler()
        ]
    )

    run_async(init())

    @bot.event
    async def on_ready() -> None:
        logging.info(f'Logged in as {bot.user}')

        try:
            synced = await bot.tree.sync()
            logging.info(f"Synced {len(synced)} command(s)")
        except Exception as error:
            logging.error(f"An error occurred during syncing: {error}")

        await connect_nodes()

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name='test'
        )
        await bot.change_presence(activity=activity)

    asyncio.run(setup_bot(bot=bot))

    try:
        bot.run(token=bot_config['token'])
    except Exception as error:
        logging.error(f"An error occurred while running the bot: {error}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        node = wavelink.NodePool.get_connected_node()
        if node:
            asyncio.run(node._session.close())
        asyncio.run(Tortoise.close_connections())
    finally:
        node = wavelink.NodePool.get_connected_node()
        if node:
            asyncio.run(node._session.close())
        asyncio.run(Tortoise.close_connections())
