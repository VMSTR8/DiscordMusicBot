from discord import Interaction, app_commands
from discord.app_commands.errors import MissingPermissions

from error_handlers.custom_exceptions import (
    BotCalledFromDirectMessageError,
    UserVoiceChannelError,
    DifferentVoiceChannelsError,
    BotVoiceChannelError,
)


def play_check():
    """
    A decorator for checking if the user and bot
    are in the same voice channel before a command.

    Raises:
        UserVoiceChannelError: If the user is not
        connected to a voice channel.
        DifferentVoiceChannelsError: If the user and bot are not
        in the same voice channel.
    """
    async def predicate(interaction: Interaction) -> bool:
        """
        Check if the user and bot are in the same
        voice channel before a command.

        Args:
            interaction (Interaction): The interaction context.

        Returns:
            bool: True if the checks passed, False otherwise.
        """
        if not interaction.guild:
            raise BotCalledFromDirectMessageError(
                'User called the bot from a direct message'
            )
        elif not interaction.user.voice:
            raise UserVoiceChannelError(
                'User is not connected to a voice channel!'
            )
        try:
            if interaction.guild.voice_client.channel.id \
                    != interaction.user.voice.channel.id:
                raise DifferentVoiceChannelsError(
                    'Bot and user are not in the same voice channel!'
                )
        except AttributeError:
            return True
        return True
    return app_commands.check(predicate)


def voice_channel_check():
    """
    A decorator for checking if the user and bot are
    in the same voice channel before a command.

    Raises:
        UserVoiceChannelError: If the user is not
        connected to a voice channel.
        BotVoiceChannelError: If the bot is not
        connected to a voice channel.
        DifferentVoiceChannelsError: If the user and bot are
        not in the same voice channel.
    """
    async def predicate(interaction: Interaction) -> bool:
        """
        Check if the user and bot are in the same
        voice channel before a command.

        Args:
            interaction (Interaction): The interaction context.

        Returns:
            bool: True if the checks passed, False otherwise.
        """
        if not interaction.guild:
            raise BotCalledFromDirectMessageError(
                'User called the bot from direct messages!'
            )
        elif not interaction.user.voice:
            raise UserVoiceChannelError(
                'User is not connected to a voice channel!'
            )
        elif not interaction.guild.voice_client:
            raise BotVoiceChannelError(
                'Bot is not connected to a voice channel!'
            )
        try:
            if interaction.guild.voice_client.channel.id \
                    != interaction.user.voice.channel.id:
                raise DifferentVoiceChannelsError(
                    'Bot and user are not in the same voice channel!'
                )
        except AttributeError:
            return True
        return True
    return app_commands.check(predicate)


def user_interaction_check():
    """
    A decorator for checking if the user is interacting
    with the bot in a guild context.

    Raises:
        BotCalledFromDirectMessageError: If the user called
        the bot from direct messages.
    """
    async def predicate(interaction: Interaction):
        """
        Check if the user is interacting with the bot in a guild context.

        Args:
            interaction (Interaction): The interaction context.

        Returns:
            bool: True if the checks passed, False otherwise.
        """
        if not interaction.guild:
            raise BotCalledFromDirectMessageError(
                'User called the bot from direct messages!'
            )
        return True
    return app_commands.check(predicate)


async def error_handler(interaction: Interaction, error) -> None:
    """
    Handle errors and send appropriate error messages.

    Args:
        interaction (Interaction):
        The interaction where the error occurred.
        error: The error that occurred.
    """
    if isinstance(error, BotCalledFromDirectMessageError):
        await interaction.response.send_message(
            'Мои команды возможно вызывать только на '
            'сервере, где я нахожусь!',
            ephemeral=True,
        )
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
    if isinstance(error, MissingPermissions):
        await interaction.response.send_message(
            '*Смотрит на тебя с презрением* У тебя даже '
            'прав администратора нет, а ты пытаешься '
            'воспользоваться этой командой...\n'
            'Ну или ты пытаешься вызвать админ-команду '
            'через личные сообщения со мной.\nДурак...',
            ephemeral=True
        )
