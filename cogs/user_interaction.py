import re

import time

import random

from urllib.parse import urlparse

from typing import Union, List

from collections import deque

import aiohttp

import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands

from database.user.db_handler import (
    add_waifu_to_user,
    check_user_waifu_link_exists,
    get_user_waifus,
    get_user,
    get_waifu_by_url,
    check_user_waifu_connection,
    set_true_love,
    remove_true_love,
    count_waifus,
)

from cogs.config import (
    general_permissions,
    voice_channel_permissions,
    text_channel_permissions
)

from settings.settings import (
    DISCORD_VOICE_CATEGORIES_ID,
    DISCORD_TEXT_CATEGORIES_ID,
    GREETINGS_CHANNEL,
)

from cogs.answers import USER_INTERACTION_ANSWERS


class PaginatorView(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed]) -> None:

        super().__init__(timeout=300)

        self._embeds = embeds
        self._queue = deque(embeds)
        self._initial = embeds[0]
        self._len = len(embeds)
        self._current_page = 1
        self.children[0].disabled = True

        if self._current_page == self._len:
            self.children[1].disabled = True

        self._queue[0].set_footer(
            text=f'Текущая страница: {self._current_page} из {self._len}'
        )

    async def on_timeout(self):
        embed = discord.Embed(
            title='Время истекло - ТОП вайфу был закрыт',
            description='Чтобы еще раз посмотреть рейтинг '
            'вызови команду /top_waifu',
            color=0x334873
        )
        await self.message.edit(embed=embed, view=None)

    async def update_buttons(self, interaction: Interaction) -> None:
        for i in self._queue:
            i.set_footer(
                text=f'Текущая страница: {self._current_page} из {self._len}')
        if self._current_page == self._len:
            self.children[1].disabled = True
        else:
            self.children[1].disabled = False

        if self._current_page == 1:
            self.children[0].disabled = True
        else:
            self.children[0].disabled = False

        await interaction.message.edit(view=self)

    @discord.ui.button(
        label='Предыдущая страница',
        style=ButtonStyle.blurple,
        emoji='⏮'
    )
    async def previous(self, interaction: Interaction, _):
        self._queue.rotate(1)
        embed = self._queue[0]
        self._current_page -= 1
        await self.update_buttons(interaction=interaction)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        label='Следующая страница',
        style=ButtonStyle.blurple,
        emoji='⏭'
    )
    async def next(self, interaction: Interaction, _):
        self._queue.rotate(-1)
        embed = self._queue[0]
        self._current_page += 1
        await self.update_buttons(interaction=interaction)
        await interaction.response.edit_message(embed=embed)

    @property
    def initial(self) -> discord.Embed:
        return self._initial


class UserInteractionCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:

        self.bot = bot
        self.shikimore_chars = re.compile(
            r'''
            https://shikimori\.(me|one)
            /characters/
            (\w+)-
            ''',
            re.X
        )

    async def is_role_exist(
            self,
            interaction: Interaction,
            role: str
    ) -> Union[None, str]:
        return discord.utils.get(
            interaction.guild.roles,
            name=role.lower().strip()
        )

    async def get_character(self, character_id: int) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f'https://shikimori.one/api/characters/{character_id}'
                )
                return {
                    'status': response.status,
                    'data': await response.json()
                }
        except aiohttp.ClientResponseError:
            return None

    async def create_role_and_permission(
            self,
            interaction: Interaction,
            role_name: str
    ) -> None:
        new_role = await interaction.guild.create_role(
            name=role_name.lower().strip(),
            color=discord.Color(random.randint(0, 0xFFFFFF)),
            hoist=True
        )
        new_role.hoist

        await interaction.user.add_roles(new_role)

        voice_categories_id = DISCORD_VOICE_CATEGORIES_ID.split(',')
        text_categories_id = DISCORD_TEXT_CATEGORIES_ID.split(',')

        for voice_category_id in voice_categories_id:
            voice_category = interaction.guild.get_channel(
                int(voice_category_id)
            )
            await voice_category.set_permissions(
                new_role,
                **general_permissions,
                **voice_channel_permissions
            )

        for text_сategory_id in text_categories_id:
            text_category = interaction.guild.get_channel(
                int(text_сategory_id)
            )
            await text_category.set_permissions(
                new_role,
                **general_permissions,
                **text_channel_permissions
            )

        await interaction.followup.send(
            USER_INTERACTION_ANSWERS[
                'role_permission_created'
            ].format(role_name=role_name.capitalize())
        )

    async def checks_before_grant_permission(
            self,
            interaction: Interaction,
            role: str,
            urls: List[str]
    ) -> None:
        if len(urls) != 5:
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['url_len_err']
            )
            return

        valid_urls = []
        for url in urls:
            if re.search(self.shikimore_chars, url):
                valid_urls.append(url)
            else:
                await interaction.followup.send(
                    USER_INTERACTION_ANSWERS[
                        'shikimori_url_valid_err'
                    ].format(url=url)
                )
                return

        if len(valid_urls) != len(set(valid_urls)):
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['unique_waifu_err']
            )
            return

        for url in valid_urls:
            character_id = re.search(self.shikimore_chars, url).group(2)
            character_id = re.sub(r'\D', '', character_id)

            discord_id = interaction.user.id
            character = await self.get_character(character_id=character_id)
            waifu_data = character['data']

            if character:
                if character['status'] == 404:
                    await interaction.followup.send(
                        USER_INTERACTION_ANSWERS[
                            'waifu_not_found'
                        ].format(url=url)
                    )
                    return
                elif character['status'] in [200, 302]:
                    await add_waifu_to_user(
                        discord_id=discord_id,
                        waifu_data=waifu_data
                    )
                else:
                    await interaction.followup.send(
                        USER_INTERACTION_ANSWERS['shikimori_unknown_message']
                    )
                    return
            else:
                await interaction.followup.send(
                    USER_INTERACTION_ANSWERS['shikimori_unknown_message']
                )
                return

        await self.create_role_and_permission(
            interaction=interaction,
            role_name=role
        )

    @commands.Cog.listener()
    async def on_member_join(self, member) -> None:
        current_hour = time.localtime().tm_hour
        if 6 <= current_hour < 12:
            current_hour = 'Ohayou'
        elif 12 <= current_hour < 18:
            current_hour = 'Konnichiwa'
        elif 18 <= current_hour < 23:
            current_hour = 'Konbanwa'
        else:
            current_hour = 'Oyasumi nasai'
        nickname = member.mention
        greetings_channel = await self.bot.fetch_channel(GREETINGS_CHANNEL)
        await greetings_channel.send(
            USER_INTERACTION_ANSWERS[
                'greetings'
            ].format(
                nickname=nickname,
                current_hour=current_hour
            )
        )

    @app_commands.command(
        name='grant_permission',
        description='Отправить список из 5 вайфу с сайта '
        'shikimori.me для получения доступа в голосовые каналы'
    )
    @app_commands.describe(
        role='Напиши название своей роли, '
        'которую я создам и присвою тебе',
        shikimori_urls='Ссылки на 5 вайфу с сайта '
        'shikimori.me через запятую'
    )
    async def grant_permission(
            self,
            interaction: Interaction,
            role: str,
            *,
            shikimori_urls: str) -> None:
        await interaction.response.defer()

        discord_id = interaction.user.id
        existing_wiafu_list = await check_user_waifu_link_exists(
            discord_id=int(discord_id)
        )

        if existing_wiafu_list:
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['adding_waifu_err']
            )
            return

        existing_role = await self.is_role_exist(
            interaction=interaction,
            role=role
        )
        if existing_role:
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS[
                    'role_already_exists'
                ].format(role=role.capitalize()),
            )
            return

        urls = [url.strip() for url in shikimori_urls.split(',')]
        await self.checks_before_grant_permission(
            interaction=interaction,
            role=role,
            urls=urls
        )

    @app_commands.command(
        name='show_my_waifus',
        description='Показать добавленных вайфу'
    )
    async def show_my_waifus(self, interaction: Interaction):
        await interaction.response.defer()

        discord_id = interaction.user.id
        username = interaction.user.display_name

        waifus = await get_user_waifus(discord_id=discord_id)
        if not waifus:
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['show_my_waifu_err']
            )
            return

        embed = discord.Embed(title=f'Список вайфу {username}', color=0x334873)

        for number, waifu_link in enumerate(waifus, start=1):
            waifu = waifu_link.waifu
            field_value = (
                f'Ссылка: https://shikimori.me{waifu.url}\n'
                f'Еще известна, как: {waifu.alt_name}\n'
                f'Имя на японском: {waifu.japanese_name}\n'
                f'Shikimori ID: {waifu.shikimori_id}'
            )

            if waifu_link.true_love:
                field_value = (
                    f'`❤️ TRUE LOVE ❤️` '
                    f'Выбрана самой любимой вайфу у {username}\n{field_value}'
                )

            embed.add_field(
                name=f'{number}. Имя: **{waifu.waifu_name_rus}**',
                value=field_value,
                inline=False
            )

        embed.set_footer(
            text='Ты можешь добавить лейбл True Love '
            'вызовом команды /true_love'
        )

        await interaction.followup.send(
            embed=embed
        )

    @app_commands.command(
        name='true_love',
        description='Добавить лейбл True Love для одной из твоих вайфу'
    )
    @app_commands.describe(
        waifu_url='Отправь ссылку на ранее добавленную вайфу'
    )
    async def true_love(self, interaction: Interaction, waifu_url: str):
        waifu_url = urlparse(waifu_url)
        discord_id = interaction.user.id
        user = await get_user(discord_id=discord_id)
        waifu = await get_waifu_by_url(waifu_url=waifu_url.path)

        if not user:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS['true_love_no_user_err'],
                ephemeral=True
            )
            return

        if not waifu:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS['true_love_url_err'],
                ephemeral=True
            )
            return

        user_waifu_connection = await check_user_waifu_connection(
            user=user,
            waifu=waifu
        )
        if not user_waifu_connection:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS['user_waifu_no_connection'],
                ephemeral=True
            )
            return

        await set_true_love(user=user, waifu=waifu)
        await interaction.response.send_message(
            USER_INTERACTION_ANSWERS[
                'added_true_love'
            ].format(waifu=waifu.waifu_name_rus),
            ephemeral=True
        )

    @app_commands.command(
        name='delete_true_love',
        description='Удалить лейбл True Love, установленный '
        'на одной из твоих вайфу'
    )
    async def delete_true_love(self, interaction: Interaction):
        discord_id = interaction.user.id
        user = await get_user(discord_id=discord_id)

        if not user:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS['delete_true_love_user_err'],
                ephemeral=True
            )
            return

        await remove_true_love(user=user)
        await interaction.response.send_message(
            USER_INTERACTION_ANSWERS['deleted_true_love'],
            ephemeral=True
        )

    @app_commands.command(
        name='top_waifu',
        description='Показать рейтинг вайфу по '
        'кол-ву добавлений пользователями'
    )
    async def waifu_top(self, interaction: Interaction):
        waifus = await count_waifus()
        string_to_add = ['🥇', '🥈', '🥉']

        if not waifus:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS['top_waifu_err'],
                ephemeral=True
            )
            return

        if len(waifus) >= len(string_to_add):
            for i in range(len(string_to_add)):
                waifus[i][0] = f'{string_to_add[i]} {waifus[i][0]}'

        embeds = []
        for waifu_chunk in discord.utils.as_chunks(waifus, 10):
            filtered_title = re.sub(r'[^\w\s\d]', '', waifus[0][0])
            embed = discord.Embed(
                title=f'Самая популярная вайфу сервера:'
                f'\n{filtered_title.strip()}',
                url=f'https://shikimori.me{waifus[0][3]}',
                description=f'Так же известна, '
                f'как: {waifus[0][2]}\n'
                f'Имя на японском: {waifus[0][5]}\n\n', color=0x334873
            )
            embed.set_author(
                name='ТОП вайфу по кол-ву добавлений пользователями')

            for value in waifu_chunk:
                embed.add_field(
                    name=f'**{value[0]}**',
                    value=f'`Кол-во добавлений: '
                    f'{value[1]}`\n=====================',
                    inline=False
                )
            embed.set_thumbnail(url=f'https://shikimori.me{waifus[0][4]}')
            embeds.append(embed)

        view = PaginatorView(embeds)
        await interaction.response.send_message(embed=view.initial, view=view)
        view.message = await interaction.original_response()
