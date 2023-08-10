from discord import app_commands, Interaction
from discord.ext import commands


class UserInteractionCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:

        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member) -> None:
        pass

    @app_commands.command(
        name='grant_permission',
        description='Отправить список из 5 вайфу с сайта '
        'shikimori.me для получения доступа в голосовые каналы'
    )
    @app_commands.describe(
        role='Напиши название своей роли, '
        'которую я создам и присвою тебе',
        shikimori_urls='Ссылки на 5 вайфу с сайта '
        'shikimori.me через запятую. Первой всегда идет твоя самая-самая!'
    )
    async def grant_permission(
            self,
            interaction: Interaction,
            role: str,
            shikimori_urls: str) -> None:
        pass
