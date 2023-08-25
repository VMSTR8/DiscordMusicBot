import logging

from discord import app_commands, Interaction
from discord.ext import commands
from discord.app_commands.errors import MissingPermissions


class AdminCog(commands.Cog):
    '''
    A cog containing administrative commands.
    '''

    def __init__(self, bot: commands.Bot) -> None:
        '''
        Initialize the AdminCog.

        Args:
            bot (commands.Bot): The bot instance.
        '''
        self.bot = bot

    @app_commands.command(
        name='send_message',
        description='[Админ-команда] Отправить сообщение '
        'от имени бота в указанный канал'
    )
    @app_commands.describe(
        channel_id='Вставь сюда ID канала, куда отправить сообщение',
        message='Напиши сообщение, которое отправит бот',
        message_id='Вставь сюда ID сообщения, которое бот должен переслать'
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def send_message(
        self,
        interaction: Interaction,
        channel_id: str,
        message: str = None,
        message_id: str = None
    ) -> None:
        '''
        Command to send a message on behalf of the bot to the specified channel.

        Args:
            interaction (Interaction): The interaction context.
            channel_id (str): The ID of the channel to send the message to.
            message (str, optional): The message content to send. Defaults to None.
            message_id (str, optional): The ID of the message to forward. Defaults to None.
        '''
        await interaction.response.defer(ephemeral=True)

        if not message and not message_id:
            await interaction.followup.send(
                'Необходимо указать сообщение или ID сообщения.'
            )

            return

        try:
            guild = interaction.guild
            channel = self.bot.get_channel(int(channel_id))

            if message_id:
                found_message = None
                for search_message in guild.text_channels:
                    try:
                        found_message = await search_message.fetch_message(
                            int(message_id)
                        )
                        break
                    except Exception as error:
                        logging.error(
                            f'Nothing was found: {error}'
                        )
                if not found_message:
                    await interaction.followup.send(
                        'Не удалось найти сообщение с указанным ID.'
                    )
                    return
                message_content = found_message.content
                attachments = found_message.attachments
            else:
                message_content = message
                attachments = []

            await channel.send(
                content=message_content,
                files=[
                    await attachment.to_file()
                    for attachment in attachments
                ]
            )
            await interaction.followup.send(
                f'Сообщение успешно отправлено в {channel.mention}.'
            )
        except Exception as error:
            await interaction.followup.send(
                f'Произошла ошибка при выполнении команды: {error}'
            )

    @send_message.error
    async def send_message_error(
        self,
        interaction: Interaction, error
    ) -> None:
        '''
        Error handler for the send_message command.

        Args:
            interaction (Interaction): The interaction context.
            error: The error raised.
        '''
        if isinstance(error, MissingPermissions):
            await interaction.response.send_message(
                '*Смотрит на тебя с презрением* У тебя даже '
                'прав администратора нет, а ты пытаешься '
                'воспользоваться этой командой...',
                ephemeral=True
            )
