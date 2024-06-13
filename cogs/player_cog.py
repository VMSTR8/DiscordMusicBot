import asyncio

import logging

from typing import (
    cast,
    Any,
    Callable,
    Optional,
)

from datetime import timedelta

from functools import wraps

import random

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from discord.errors import (
    Forbidden,
    InteractionResponded,
    NotFound
)

import wavelink
from wavelink.exceptions import LavalinkLoadException

from error_handlers.errors import (
    play_check,
    error_handler,
)

from cogs.answers import PLAYER_BUTTONS_ERROR


def same_channel_check(func: Callable) -> Callable:
    """
    Decorator to check if the user
    is in the same voice channel as the bot.

    Args:
        func (Callable): The function to wrap.

    Returns:
        Callable: The wrapped function.
    """
    @wraps(func)
    async def wrapper(
        self: Any,
        interaction: Interaction,
        *args: Any,
        **kwargs: Any
    ) -> Optional[Callable]:
        user_voice_channel = (
            interaction.user.voice.channel
            if interaction.user.voice else None
        )
        bot_voice_channel = (
            interaction.guild.voice_client.channel
            if interaction.guild.voice_client else None
        )

        if user_voice_channel and bot_voice_channel \
                and user_voice_channel == bot_voice_channel:
            return await func(self, interaction, *args, **kwargs)
        else:
            await interaction.response.edit_message(view=self)
            try:
                await interaction.user.send(
                    random.choice(PLAYER_BUTTONS_ERROR),
                    file=discord.File(
                        'bot_images/player/buttons_error/angry.jpg'
                    ),
                    delete_after=60.0
                )
            except Forbidden:
                pass
            return

    return wrapper


class PlayerControls(discord.ui.View):
    """
    A class representing the music control UI for a Discord bot.

    Attributes:
        player (wavelink.Player): The player instance.
        volume (int): The current volume of the player.
        embed (discord.Embed): The embed associated with the controls.
    """

    def __init__(self, player: wavelink.Player, embed: discord.Embed) -> None:
        """
        Initialize the MusicControls view.

        Args:
            player (wavelink.Player): The player instance.
            embed (discord.Embed): The embed associated with the controls.
        """
        super().__init__(timeout=None)
        self.player: wavelink.Player = player
        self.embed: discord.Embed = embed

        self.lock: asyncio.Lock = asyncio.Lock()

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str(
            '<:botrewind:1250613904933912687>'),
        style=discord.ButtonStyle.blurple
    )
    @same_channel_check
    async def rewind(
        self,
        interaction: Interaction,
        button: discord.ui.Button,
    ) -> None:
        """
        Handle the rewind button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        async with self.lock:
            current_position = self.player.position
            new_position = max(0, current_position - 10000)
            await self.player.seek(new_position)
            await interaction.response.edit_message(view=self)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str('<:botstop:1250613906532204564>'),
        style=discord.ButtonStyle.blurple
    )
    @same_channel_check
    async def stop(
        self,
        interaction: Interaction,
        button: discord.ui.Button
    ) -> None:
        """
        Handle the stop button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        async with self.lock:
            self.player.queue.clear()
            await self.player.stop(force=False)
            await self.player.disconnect()

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str('<:botpause:1250613901842845696>'),
        style=discord.ButtonStyle.blurple
    )
    @same_channel_check
    async def pause(
        self,
        interaction: Interaction,
        button: discord.ui.Button
    ) -> None:
        """
        Handle the play/pause button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        async with self.lock:
            await self.player.pause(not self.player.paused)

            if self.player.paused:
                button.emoji = discord.PartialEmoji.from_str(
                    '<:botplay:1250613903470100490>')
                button.style = discord.ButtonStyle.success
            else:
                button.emoji = discord.PartialEmoji.from_str(
                    '<:botpause:1250613901842845696>')
                button.style = discord.ButtonStyle.blurple
            await interaction.response.edit_message(view=self)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str(
            '<:botfastforward:1250613898374152252>'),
        style=discord.ButtonStyle.blurple
    )
    @same_channel_check
    async def fast_forward(
        self,
        interaction: Interaction,
        button: discord.ui.Button,
    ) -> None:
        """
        Handle the fast forward button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        async with self.lock:
            current_position = self.player.position
            new_position = current_position + 10000
            try:
                if new_position >= self.player.current.length:
                    if self.player.queue:
                        await self.player.skip()
                else:
                    await self.player.seek(new_position)
            except AttributeError:
                await interaction.response.edit_message(view=None)

            try:
                await interaction.response.edit_message(view=self)
            except NotFound:
                await interaction.response.edit_message(view=self)
            except InteractionResponded:
                await self.player.disconnect()

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str('<:botskip:1250613899733110960>'),
        style=discord.ButtonStyle.blurple
    )
    @same_channel_check
    async def skip(
        self,
        interaction: Interaction,
        button: discord.ui.Button
    ) -> None:
        """
        Handle the skip button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        async with self.lock:
            if self.player.queue:
                await self.player.skip()
                await interaction.response.edit_message(view=self)
            else:
                await self.player.stop()
                await self.player.disconnect()


class PlayerCog(commands.Cog):
    """
    A cog containing commands for music playback in voice channels.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the MusicCog.

        Args:
            bot (commands.Bot): The bot instance.
        """
        self.bot = bot

        self.channel: Optional[discord.TextChannel] = None
        self.message: Optional[discord.Message] = None
        self.embed: Optional[discord.Embed] = None
        self.track_volume: int = 100
        self.view: type[PlayerControls] = PlayerControls

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> None:
        """
        Event listener for when a voice state updates.

        Args:
            member (discord.Member): The member whose voice state updated.
            before (discord.VoiceState): The state before the update.
            after (discord.VoiceState): The state after the update.
        """
        if member == self.bot.user and before.channel and not after.channel:
            if self.message:
                try:
                    await self.message.delete()
                except NotFound:
                    pass
                self.message = self.channel = self.embed = None

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """
        Event listener for when a wavelink node becomes ready.

        Args:
            node (wavelink.Node): The wavelink node that became ready.
        """
        logging.info(f'Node {node.node.uri} ready.')

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self,
        payload: wavelink.TrackStartEventPayload
    ) -> None:
        """
        Event listener for when a wavelink track starts playing.

        Args:
            payload (wavelink.TrackStartEventPayload): The track event payload.
        """
        player: wavelink.Player | None = payload.player
        if not player:
            return

        track: wavelink.Playable = payload.track
        track_duration = str(timedelta(milliseconds=track.length))
        if '.' in track_duration:
            track_duration = track_duration.split('.')[0]
        description = track.title

        queue = 'Очередь пуста'

        if player.queue:
            queue = ''.join(
                [f'{iteration + 1}. {track.author} - {track.title}\n'
                    for iteration, track in enumerate(player.queue[:5])]
            )
        author = track.author if track.artist else track.author

        footer_icon = discord.File(
            'bot_images/player/headphones.png',
            filename='headphones.png'
        )
        embed = discord.Embed(
            title='Сейчас играет',
            description=description,
            color=0x9966cc
        )

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.add_field(
            name='Исполнитель',
            value=f'`{author}`',
            inline=True
        )
        embed.add_field(
            name='Продолжительность',
            value=f'`{track_duration}`',
            inline=True
        )
        embed.add_field(
            name='В очереди',
            value=f'`{len(player.queue)}`',
            inline=True
        )
        embed.add_field(
            name='Очередь [первые 5 позиций]',
            value=f'{queue}',
            inline=False
        )
        embed.set_footer(
            text=(
                'Если очередь воспроизведения пустая,\n'
                'то через 1 минуту я сама покину голосовой канал!'
            ),
            icon_url='attachment://headphones.png'
        )
        self.embed = embed

        view = self.view(player=player, embed=embed)

        if not self.message:
            self.message = await self.channel.send(
                embed=embed,
                view=view,
                file=footer_icon
            )
        else:
            await asyncio.sleep(0.2)
            await self.message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(
        self,
        player: wavelink.Player
    ) -> None:
        """
        Event listener for when a wavelink player becomes inactive.

        Args:
            player (wavelink.Player): The inactive player.
        """
        await player.disconnect()

    @app_commands.command(
        name='play',
        description='Воспроизведение/добавление в очередь музыки',
    )
    @app_commands.describe(
        song='Напиши название песни или отправь ссылку на песню!'
    )
    @commands.guild_only()
    @play_check()
    async def play(
        self,
        interaction: Interaction,
        *,
        song: str
    ) -> None:
        """
        Play a song.

        Args:
            interaction (Interaction): The interaction context.
            song (str): The song to search for and play.
        """
        self.channel = interaction.channel
        destination = interaction.user.voice.channel

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(song)
            if not tracks:
                await interaction.response.send_message(
                    'К сожалению, я не смогла ничего найти :(',
                    ephemeral=True
                )
                return
        except LavalinkLoadException:
            await interaction.response.send_message(
                'К сожалению, я не смогла ничего найти :(\n'
                'Может быть ссылка неправильная? '
                'Или источник поиска?',
                ephemeral=True
            )
            return

        if not interaction.guild.voice_client:
            await destination.connect(
                cls=wavelink.Player,
                self_deaf=True,
            )

        player: wavelink.Player = cast(
            wavelink.Player,
            interaction.guild.voice_client
        )

        player.autoplay = wavelink.AutoPlayMode.partial
        player.inactive_timeout = 60

        track: wavelink.Playable = tracks[0]

        await player.queue.put_wait(track)

        view = self.view(player=player, embed=self.embed)

        if not player.playing:
            await player.play(player.queue.get(), volume=self.track_volume)
            await interaction.response.send_message(
                f'Включила **{track.title}**!',
                ephemeral=True,
                delete_after=10.0
            )
        else:
            queue = ''.join(
                [f'{iteration + 1}. {track.author} - {track.title}\n'
                 for iteration, track in enumerate(player.queue[:5])]
            )
            self.embed.set_field_at(
                2,
                name='В очереди',
                value=f'`{len(player.queue)}`',
                inline=True
            )
            self.embed.set_field_at(
                3,
                name='Очередь [первые 5 позиций]',
                value=f'{queue}',
                inline=False
            )
            await self.message.edit(embed=self.embed, view=view)
            await interaction.response.send_message(
                f'Добавила в очередь **{track.title}**!',
                ephemeral=True,
                delete_after=10.0
            )

    @play.error
    async def play_error(self, interaction: Interaction, error) -> None:
        """
        Error handler for the play command.

        Args:
            interaction (Interaction): The interaction context.
            error (Exception): The error that occurred.
        """
        await error_handler(interaction, error)
