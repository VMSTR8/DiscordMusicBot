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
    MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID,
)


class DiscordBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.all()
        intents.voice_states = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(intents=intents, command_prefix='!')

    async def connect_nodes(self) -> None:
        await self.wait_until_ready()
        try:
            node: wavelink.Node = wavelink.Node(
                uri=WAVELINK_URI,
                password=WAVELINK_PASSWORD,
                secure=False,
                retries=5
            )
            await wavelink.NodePool.connect(client=self, nodes=[node])
        except aiohttp.client_exceptions.ClientConnectorError as error:
            logging.error(f'An error occurred while connecting nodes: {error}')
            await node._session.close()
            await self.close()

    async def setup_hook(self) -> None:
        await self.add_cog(MusicCog(bot=self))
        await self.add_cog(UserInteractionCog(bot=self))

        try:
            synced = await self.tree.sync()
            logging.info(f'Synced {len(synced)} command(s)')
        except Exception as error:
            logging.error(f'An error occurred during syncing: {error}')

    async def on_ready(self):
        logging.info(f'Logged in as {self.user}')

        await self.connect_nodes()

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name='на тебя с презрением'
        )
        await self.change_presence(activity=activity)

    async def on_message(self, message):
        if message.channel.id in [
            int(channel_id)
            for channel_id in MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID.split(',')
        ] and not message.author.bot:
            await message.delete()

    async def close_connections(self):
        try:
            node: wavelink.Node = wavelink.NodePool.get_node()
            await node._session.close()
        except wavelink.exceptions.InvalidNode:
            logging.error('No Nodes established')
        await Tortoise.close_connections()


bot = DiscordBot()


def main() -> None:

    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_file_name = datetime.now().strftime('log_%Y_%m_%d_%H_%M.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
                logging.FileHandler(os.path.join('logs', log_file_name)),
                logging.StreamHandler()
        ]
    )

    run_async(init())
    bot.run(BOT_TOKEN)


if __name__ == '__main__':
    try:
        main()
    finally:
        asyncio.run(bot.close_connections())
