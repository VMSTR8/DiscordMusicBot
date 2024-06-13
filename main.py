import os

import asyncio

import logging

from datetime import datetime

import discord
from discord.ext import commands

import wavelink
from wavelink import NodeStatus

from tortoise import run_async, Tortoise

from database.init import init

from cogs.player_cog import PlayerCog
from cogs.user_interaction_cog import UserInteractionCog
from cogs.admin_cog import AdminCog

from settings.settings import (
    BOT_TOKEN,
    WAVELINK_URI,
    WAVELINK_PASSWORD,
    MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID,
)


class DiscordBot(commands.Bot):
    """
    Custom Discord bot class inheriting from `commands.Bot`.

    Attributes:
        intents (discord.Intents): The intents for the bot's functionality.

    Methods:
        connect_nodes(): Connects to the Wavelink nodes.
        setup_hook(): Sets up cogs and syncs commands.
        on_ready(): Event handler when the bot is ready.
        on_message(message): Event handler for incoming messages.
        close_connections(): Closes connections and resources
        when the bot is shutting down.
    """

    def __init__(self):
        intents = discord.Intents.all()
        intents.voice_states = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(intents=intents, command_prefix='!')

    async def connect_nodes(self) -> None:
        """
        Connects to Wavelink nodes.
        """
        await self.wait_until_ready()

        node: wavelink.Node = wavelink.Node(
            uri=WAVELINK_URI,
            password=WAVELINK_PASSWORD,
            retries=5
        )
        await wavelink.Pool.connect(client=self, nodes=[node])

        if node.status == NodeStatus.DISCONNECTED:
            logging.error('An error occurred while connecting nodes')
            await node._session.close()
            await self.close()

    async def setup_hook(self) -> None:
        """
        Sets up cogs and syncs commands.

        Raises:
            Exception: If an error occurs during command syncing.
        """
        await self.add_cog(PlayerCog(bot=self))
        await self.add_cog(UserInteractionCog(bot=self))
        await self.add_cog(AdminCog(bot=self))

        try:
            synced = await self.tree.sync()
            logging.info(f'Synced {len(synced)} command(s)')
        except Exception as error:
            logging.error(f'An error occurred during syncing: {error}')

    async def on_ready(self) -> None:
        """
        Event handler when the bot is ready.
        """
        logging.info(f'Logged in as {self.user}')

        await self.connect_nodes()

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name='на тебя с презрением'
        )
        await self.change_presence(activity=activity)

    async def on_message(self, message: discord.Message) -> None:
        """
        Event handler for incoming messages.

        Args:
            message (discord.Message): The incoming message.

        Note:
        Deletes the message if it's from a restricted
        channel and not sent by a bot.
        """
        if message.channel.id in [
            int(channel_id)
            for channel_id in MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID.split(',')
        ] and not message.author.bot:
            await message.delete()

    async def close_connections(self) -> None:
        """
        Closes connections and resources when the bot is shutting down.
        """
        try:
            node: wavelink.Node = wavelink.Pool.get_node()
            await node._session.close()
        except wavelink.exceptions.InvalidNodeException:
            logging.error('No Nodes established')
        await Tortoise.close_connections()
        await self.close()


bot = DiscordBot()


def main() -> None:
    """
    Main function to start the bot.

    Note:
        Initializes logging, runs database initialization, and starts the bot.
    """
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
