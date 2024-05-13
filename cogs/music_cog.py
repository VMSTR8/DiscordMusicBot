import logging

from typing import cast

from datetime import timedelta

import discord
from discord import app_commands, Interaction
from discord.ext import commands

import wavelink
from wavelink.exceptions import LavalinkLoadException

from error_handlers.errors import (
    play_check,
    voice_channel_check,
    error_handler,
)


class MusicCog(commands.Cog):
    """
    A cog containing commands for music playback in voice channels.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the MusicCog.

        Args:
            bot (commands.Bot): The bot instance.
        """
        self.bot = bot

        self.channel = None
        self.track_volume = 100

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

        embed = discord.Embed(
            title='Сейчас играет',
            description=description,
            color=0x334873
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
            name='Источник',
            value=f'`{track.source.capitalize()}`',
            inline=True
        )

        await self.channel.send(embed=embed)

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

        if player.queue:
            pass
        else:
            self.channel = None
            await player.disconnect()

    @app_commands.command(
        name='play',
        description='Воспроизведение/добавление в очередь музыки',
    )
    @app_commands.describe(song='Напиши название песни или отправь ссылку на песню!')
    @play_check()
    async def play(
        self,
        interaction: Interaction,
        *,
        song: str
    ) -> None:
        """
        Command to play or enqueue music from YouTube.

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

        await interaction.response.send_message(
            f'**{track.title}** добавлено в очередь!'
        )

        if not player.playing:
            await player.play(player.queue.get(), volume=self.track_volume)

    @play.error
    async def play_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='stop',
        description='Остановить воспроизведение музыки',
    )
    @voice_channel_check()
    async def stop(
        self,
        interaction: Interaction
    ) -> None:
        """
        Command to stop music playback.

        Args:
            interaction (Interaction): The interaction context.
        """
        player: wavelink.Player = interaction.guild.voice_client

        if player.playing or player.paused:
            await player.stop(force=False)
            player.queue.clear()
            self.channel = None
            await player.disconnect()

            await interaction.response.send_message(
                'Музыка остановлена!'
            )

        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @stop.error
    async def stop_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='pause',
        description='Поставить/снять с паузы воспроизведение музыки',
    )
    @voice_channel_check()
    async def pause(
        self,
        interaction: Interaction
    ) -> None:
        """
        Command to pause or resume music playback.

        Args:
            interaction (Interaction): The interaction context.
        """
        player: wavelink.Player = interaction.guild.voice_client
        await player.pause(not player.paused)

        if player.paused:
            await interaction.response.send_message(
                'Музыка поставлена на паузу!'
            )
        else:
            await interaction.response.send_message(
                'Музыка снята с паузы!'
            )

    @pause.error
    async def pause_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='skip',
        description='Пропустить текущий трек',
    )
    @voice_channel_check()
    async def skip(
        self,
        interaction: Interaction
    ) -> None:
        """
        Command to skip the current track.

        Args:
            interaction (Interaction): The interaction context.
        """
        player: wavelink.Player = interaction.guild.voice_client

        if player.playing:

            if player.queue:
                await player.skip()
                await interaction.response.send_message(
                    'Текущий трек пропущен!'
                )

            else:
                await player.stop(force=False)
                await player.disconnect()
                await interaction.response.send_message(
                    'Текущий трек пропущен, '
                    'но другой музыки в очереди нет ¯\_(ツ)_/¯'
                )

        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @skip.error
    async def skip_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='volume',
        description='Изменить громкость '
        'воспроизведения музыки (от 0% до 100%)',
    )
    @app_commands.describe(volume='Введи число от 0 до 100')
    @voice_channel_check()
    async def volume(
        self,
        interaction: Interaction,
        volume: int
    ) -> None:
        """
        Command to change the volume of music playback.

        Args:
            interaction (Interaction): The interaction context.
            volume (int): The volume level to set (0-100).
        """
        player: wavelink.Player = interaction.guild.voice_client

        if 0 <= volume <= 100:
            self.track_volume = volume
            await player.set_volume(volume)
            await interaction.response.send_message(
                f'Громкость воспроизведения изменена на {volume}%!',
            )

        else:
            await interaction.response.send_message(
                'Громкость воспроизведения не может '
                'быть меньше 0% или больше 100%!',
                ephemeral=True,
            )

    @volume.error
    async def volume_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='np',
        description='Показать текущий трек',
    )
    @voice_channel_check()
    async def np(
        self,
        interaction: Interaction
    ) -> None:
        """
        Command to display the current playing track.

        Args:
            interaction (Interaction): The interaction context.
        """
        player: wavelink.Player = interaction.guild.voice_client

        if player.playing:

            track = player.current
            track_duration = timedelta(milliseconds=track.length)

            embed = discord.Embed(title='Сейчас играет',
                                  description=track.title,
                                  color=0x334873)
            embed.add_field(name='Продолжительность',
                            value=f"`{track_duration}`", inline=True)
            embed.add_field(name='Очередь',
                            value=f"`{len(player.queue)}`", inline=True)

            await interaction.response.send_message(embed=embed)

        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @np.error
    async def np_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='queue',
        description='Показывает до 10 следующих треков в очереди',
    )
    @voice_channel_check()
    async def queue(
        self,
        interaction: Interaction
    ) -> None:
        """
        Command to display the next 10 tracks in the queue.

        Args:
            interaction (Interaction): The interaction context.
        """
        player: wavelink.Player = interaction.guild.voice_client

        if player.playing:

            if player.queue:

                current_play = player.current

                queue = ''.join(
                    [f'{iteration + 1}. {track.author} - {track.title} \n' for iteration,
                        track in enumerate(player.queue)]
                )

                embed = discord.Embed(
                    title='Очередь воспроизведения',
                    description=f'Сейчас играет: `{current_play.title}`',
                    color=0x334873
                )
                embed.add_field(name='10 следующих треков',
                                value=f'`{queue}`', inline=True)

                await interaction.response.send_message(embed=embed)

            else:
                await interaction.response.send_message(
                    'Очередь воспроизведения пуста!',
                    ephemeral=True
                )

        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @queue.error
    async def queue_error(self, interaction: Interaction, error) -> None:
        await error_handler(interaction, error)
