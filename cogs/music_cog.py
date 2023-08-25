import re

import logging

from datetime import timedelta

import discord
from discord import app_commands, Interaction
from discord.ext import commands

import wavelink

from custom_exceptions import (
    UserVoiceChannelError,
    BotVoiceChannelError,
    DifferentVoiceChannelsError,
)


class MusicCog(commands.Cog):
    '''
    A cog containing commands for music playback in voice channels.
    '''

    def __init__(self, bot: commands.Bot):
        '''
        Initialize the MusicCog.

        Args:
            bot (commands.Bot): The bot instance.
        '''
        self.bot = bot

        self.channel = None
        self.track_volume = 100

        self.re_url = re.compile(
            r'''(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]
            {2,4}/)+(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))
            +(?:\(([^\s()<>]+|(\([^\s()<>]
            +\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))''',
            re.X
        )

    def play_check():
        '''
        A decorator for checking if the user and bot
        are in the same voice channel before a command.

        Raises:
            UserVoiceChannelError: If the user is not
            connected to a voice channel.
            DifferentVoiceChannelsError: If the user and bot are not
            in the same voice channel.
        '''
        async def predicate(interaction: Interaction) -> bool:
            '''
            Check if the user and bot are in the same
            voice channel before a command.

            Args:
                interaction (Interaction): The interaction context.

            Returns:
                bool: True if the checks passed, False otherwise.
            '''
            if not interaction.user.voice:
                raise UserVoiceChannelError(
                    'User is not connected to a voice channel!')
            try:
                if interaction.guild.voice_client.channel.id \
                        != interaction.user.voice.channel.id:
                    raise DifferentVoiceChannelsError(
                        'Bot and user are not in the same voice channel!')
            except AttributeError:
                return True
            return True
        return app_commands.check(predicate)

    def voice_channel_check():
        '''
        A decorator for checking if the user and bot are
        in the same voice channel before a command.

        Raises:
            UserVoiceChannelError: If the user is not
            connected to a voice channel.
            BotVoiceChannelError: If the bot is not
            connected to a voice channel.
            DifferentVoiceChannelsError: If the user and bot are
            not in the same voice channel.
        '''
        async def predicate(interaction: Interaction) -> bool:
            '''
            Check if the user and bot are in the same
            voice channel before a command.

            Args:
                interaction (Interaction): The interaction context.

            Returns:
                bool: True if the checks passed, False otherwise.
            '''
            if not interaction.user.voice:
                raise UserVoiceChannelError(
                    'User is not connected to a voice channel!')
            elif not interaction.guild.voice_client:
                raise BotVoiceChannelError(
                    'Bot is not connected to a voice channel!')
            try:
                if interaction.guild.voice_client.channel.id \
                        != interaction.user.voice.channel.id:
                    raise DifferentVoiceChannelsError(
                        'Bot and user are not in the same voice channel!')
            except AttributeError:
                return True
            return True
        return app_commands.check(predicate)

    async def error_handler(self, interaction: Interaction, error) -> None:
        '''
        Handle errors and send appropriate error messages.

        Args:
            interaction (Interaction):
            The interaction where the error occurred.
            error: The error that occurred.
        '''
        if isinstance(error, UserVoiceChannelError):
            await interaction.response.send_message(
                f'{interaction.user.mention}, '
                'для начала нужно зайти в голосовой канал!',
                ephemeral=True,
            )
        if isinstance(error, BotVoiceChannelError):
            await interaction.response.send_message(
                f'{interaction.user.mention}, '
                'я должна быть в голосовом канале!',
                ephemeral=True,
            )
        if isinstance(error, DifferentVoiceChannelsError):
            await interaction.response.send_message(
                f'{interaction.user.mention}, '
                'чтобы взаимодействовать с плеером, '
                'нам с тобой нужно быть в одном голосовом канале!',
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        '''
        Event listener for when a wavelink node becomes ready.

        Args:
            node (wavelink.Node): The wavelink node that became ready.
        '''
        logging.info(f'Node {node.uri} ready.')

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, player: wavelink.TrackEventPayload
    ) -> None:
        '''
        Event listener for when a wavelink track starts playing.

        Args:
            player (wavelink.TrackEventPayload): The track event payload.
        '''
        vc = player.player
        track = vc.current
        track_duration = timedelta(milliseconds=track.length)

        embed = discord.Embed(
            title='Сейчас играет',
            description=track.title,
            color=0x334873
        )
        embed.add_field(name='Продолжительность',
                        value=f'`{track_duration}`', inline=True)
        embed.add_field(name='Очередь',
                        value=f'`{len(vc.queue)}`', inline=True)

        await self.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self, player: wavelink.TrackEventPayload
    ) -> None:
        '''
        Event listener for when a wavelink track ends.

        Args:
            player (wavelink.TrackEventPayload): The track event payload.
        '''
        vc = player.player

        if vc.queue:
            pass
        else:
            self.channel = None
            await vc.disconnect()

    @app_commands.command(
        name='play',
        description='Воспроизведение/добавление в очередь музыки из YouTube',
    )
    @app_commands.describe(song='Напиши название песни. Ссылки недопустимы!')
    @play_check()
    async def play(self, interaction: Interaction, *, song: str) -> None:
        '''
        Command to play or enqueue music from YouTube.

        Args:
            interaction (Interaction): The interaction context.
            song (str): The song to search for and play.
        '''
        self.channel = interaction.channel
        destenation = interaction.user.voice.channel

        if not self.re_url.match(song):
            tracks = await wavelink.YouTubeTrack.search(song)
        else:
            await interaction.response.send_message(
                'Я ищу музыку только по текстовому запросу!',
                ephemeral=True
            )

        if tracks:
            track = tracks[0]
        else:
            await interaction.response.send_message(
                'К сожалению, я не смогла ничего найти :(',
                ephemeral=True
            )
            return

        if not interaction.guild.voice_client:
            vc: wavelink.Player = await destenation.connect(
                cls=wavelink.Player,
                self_deaf=True,
            )
        else:
            vc: wavelink.Player = interaction.guild.voice_client

        await interaction.response.send_message(
            f'**{track.title}** добавлено в очередь!'
        )

        vc.autoplay = True

        await vc.queue.put_wait(track)

        if not vc.is_playing():
            await vc.play(vc.queue.get(), volume=self.track_volume)

    @play.error
    async def play_error(self, interaction: Interaction, error) -> None:
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='stop',
        description='Остановить воспроизведение музыки',
    )
    @voice_channel_check()
    async def stop(self, interaction: Interaction) -> None:
        '''
        Command to stop music playback.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_playing() or vc.is_paused():
            await vc.stop(force=False)
            vc.queue.clear()
            self.channel = None
            await vc.disconnect()

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
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='pause',
        description='Поставить воспроизведение музыки на паузу',
    )
    @voice_channel_check()
    async def pause(self, interaction: Interaction) -> None:
        '''
        Command to pause music playback.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_playing():
            await vc.pause()
            await interaction.response.send_message(
                'Музыка поставлена на паузу!'
            )
        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @pause.error
    async def pause_error(self, interaction: Interaction, error) -> None:
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='resume',
        description='Снять воспроизведение музыки с паузы',
    )
    @voice_channel_check()
    async def resume(self, interaction: Interaction) -> None:
        '''
        Command to resume paused music playback.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_paused():
            await vc.resume()
            await interaction.response.send_message(
                'Музыка снята c паузы!'
            )
        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @resume.error
    async def resume_error(self, interaction: Interaction, error) -> None:
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='skip',
        description='Пропустить текущий трек',
    )
    @voice_channel_check()
    async def skip(self, interaction: Interaction) -> None:
        '''
        Command to skip the current track.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_playing():

            if vc.queue:
                await vc.stop()
                await interaction.response.send_message(
                    'Текущий трек пропущен!'
                )

            else:
                await vc.stop(force=False)
                await vc.disconnect()
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
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='volume',
        description='Изменить громкость '
        'воспроизведения музыки (от 0% до 100%)',
    )
    @app_commands.describe(volume='Введи число от 0 до 100')
    @voice_channel_check()
    async def volume(self, interaction: Interaction, volume: int) -> None:
        '''
        Command to change the volume of music playback.

        Args:
            interaction (Interaction): The interaction context.
            volume (int): The volume level to set (0-100).
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if 0 <= volume <= 100:
            self.track_volume = volume
            await vc.set_volume(volume)
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
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='np',
        description='Показать текущий трек',
    )
    @voice_channel_check()
    async def np(self, interaction: Interaction) -> None:
        '''
        Command to display the current playing track.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_playing():

            track = vc.current
            track_duration = timedelta(milliseconds=track.length)

            embed = discord.Embed(title='Сейчас играет',
                                  description=track.title,
                                  color=0x334873)
            embed.add_field(name='Продолжительность',
                            value=f"`{track_duration}`", inline=True)
            embed.add_field(name='Очередь',
                            value=f"`{len(vc.queue)}`", inline=True)

            await interaction.response.send_message(embed=embed)

        else:
            await interaction.response.send_message(
                'Музыка не воспроизводится!',
                ephemeral=True
            )

    @np.error
    async def np_error(self, interaction: Interaction, error) -> None:
        await self.error_handler(interaction, error)

    @app_commands.command(
        name='queue',
        description='Показывает до 10 следующих треков в очереди',
    )
    @voice_channel_check()
    async def queue(self, interaction: Interaction) -> None:
        '''
        Command to display the next 10 tracks in the queue.

        Args:
            interaction (Interaction): The interaction context.
        '''
        vc: wavelink.Player = interaction.guild.voice_client

        if vc.is_playing():

            if vc.queue:

                current_play = vc.current

                queue = ''.join(
                    [f'{iteration + 1}. {track.title} \n' for iteration,
                        track in enumerate(vc.queue)]
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
        await self.error_handler(interaction, error)
