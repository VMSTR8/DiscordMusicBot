import asyncio

import logging

from typing import (
    cast,
    Any,
    Callable,
    Optional,
    Union,
    List
)

from datetime import timedelta

from functools import wraps

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
                await interaction.user.send('Вы должны находиться в одном голосовом канале с ботом, чтобы использовать эти кнопки.')
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
        self.player = player
        self.volume = player.volume
        self.embed = embed

    @discord.ui.button(emoji='⏪')
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
        current_position = self.player.position
        new_position = max(0, current_position - 10000)
        await self.player.seek(new_position)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='⏹')
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
        self.player.queue.clear()
        await self.player.stop(force=False)

    @discord.ui.button(emoji='⏸')
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
        await self.player.pause(not self.player.paused)

        if self.player.paused:
            button.emoji = '▶️'
        else:
            button.emoji = '⏸'
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='⏩')
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
            pass

    @discord.ui.button(emoji='⏭', custom_id='player:skip')
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
        if self.player.queue:
            await self.player.skip()
        else:
            await self.player.stop()

    @discord.ui.button(emoji='🔈', custom_id='player:volume_down')
    @same_channel_check
    async def volume_down(
        self,
        interaction: Interaction,
        button: discord.ui.Button,
    ) -> None:
        """
        Handle the volume down button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        if self.volume == 0:
            await interaction.response.edit_message(view=self)
        else:
            self.volume -= 10
            await self.player.set_volume(self.volume)
            self.embed.set_field_at(
                2, name='Громкость',
                value=f'`{self.volume}%`',
                inline=True
            )
            await interaction.response.edit_message(
                view=self,
                embed=self.embed
            )

    @discord.ui.button(emoji='🔊')
    @same_channel_check
    async def volume_up(
        self,
        interaction: Interaction,
        button: discord.ui.Button,
    ) -> None:
        """
        Handle the volume up button interaction.

        Args:
            interaction (Interaction): The interaction context.
            button (discord.ui.Button): The button that was pressed.
        """
        if self.volume == 100:
            await interaction.response.edit_message(view=self)
        else:
            self.volume += 10
            await self.player.set_volume(self.volume)
            self.embed.set_field_at(
                2, name='Громкость',
                value=f'`{self.volume}%`',
                inline=True
            )
            await interaction.response.edit_message(
                view=self,
                embed=self.embed
            )


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

        self.channel = None
        self.message = None
        self.embed = None
        self.track_volume = 100

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
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

        embed = discord.Embed(
            title='Сейчас играет',
            description=description,
            color=0x9966cc
        )

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.add_field(
            name='Продолжительность',
            value=f'`{track_duration}`',
            inline=True
        )

        embed.add_field(
            name='Очередь',
            value=f'`{len(player.queue)}`',
            inline=True
        )

        embed.add_field(
            name='Громкость',
            value=f'`{player.volume}%`',
            inline=True
        )

        embed.add_field(
            name='Очередь [первые 5 позиций]',
            value=f'{queue}',
            inline=False
        )

        self.embed = embed

        view = PlayerControls(player=player, embed=embed)
        if not self.message:
            self.message = await self.channel.send(embed=embed, view=view)
        else:
            await self.message.delete()
            self.message = await self.channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self,
        payload: wavelink.TrackStartEventPayload
    ) -> None:
        """
        Event listener for when a wavelink track ends.

        Args:
            payload (wavelink.TrackStartEventPayload): The track event payload.
        """
        player: wavelink.Player | None = payload.player

        if not player:
            return

        self.track_volume = player.volume

        if player.queue:
            pass
        else:
            embed = discord.Embed(
                title='Воспроизведение завершено, плеер отключен',
                description='Чтобы включить музыку '
                'вызови команду /play',
                color=0x9966cc
            )
            await self.message.delete()
            await self.channel.send(view=None, embed=embed)
            self.channel = self.message = self.embed = None
            await player.disconnect()

    @app_commands.command(
        name='play',
        description='Воспроизведение/добавление в очередь музыки',
    )
    @app_commands.describe(
        song='Напиши название песни или отправь ссылку на песню!'
    )
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
        track: wavelink.Playable = tracks[0]

        await player.queue.put_wait(track)

        view = PlayerControls(player=player, embed=self.embed)

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
                1,
                name='Очередь',
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
