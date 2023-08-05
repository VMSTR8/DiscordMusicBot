import asyncio

import discord
from discord.ext import commands

import wavelink

from cogs.music import MusicCog

from settings.settings import (
    BOT_TOKEN,
    WAVELINK_URI,
    WAVELINK_PASSWORD,
)

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
    node: wavelink.Node = wavelink.Node(
        uri=WAVELINK_URI, password=WAVELINK_PASSWORD, secure=False)
    await wavelink.NodePool.connect(client=bot, nodes=[node])


async def setup_bot(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot=bot))


def main() -> None:

    @bot.event
    async def on_ready() -> None:

        print(f'Logged in as {bot.user}')
        synced = await bot.tree.sync()
        await connect_nodes()
        try:
            print(f"Synced {len(synced)} command(s)")
        except Exception as error:
            print(error.message)
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name='на еблю твоей мамки'
        )
        await bot.change_presence(activity=activity)

    asyncio.run(setup_bot(bot=bot))

    bot.run(token=bot_config['token'])


if __name__ == '__main__':
    main()
