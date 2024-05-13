import re

import time

import random

from urllib.parse import urlparse

from typing import Optional, List, Dict, Any

from collections import deque

import logging

import aiohttp

import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands
from discord.errors import Forbidden

from error_handlers.errors import (
    error_handler,
    user_interaction_check,
)

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
    remove_user_and_userwaifulinks,
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
    """
    A custom paginator view for displaying embeds with navigation buttons.

    Attributes:
        _embeds (List[discord.Embed]): List of embeds to display.
        _queue (deque): A queue to hold the embeds for navigation.
        _initial (discord.Embed): The initial embed to display.
        _len (int): The total number of embeds.
        _current_page (int): The current page being displayed.
    """

    def __init__(self, embeds: List[discord.Embed]) -> None:
        """
        Initialize the PaginatorView.

        Args:
            embeds (List[discord.Embed]): List of embeds to display.
        """

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

    async def on_timeout(self) -> None:
        """
        Handle the timeout event when no interaction happens.

        Updates the message with a timeout message and removes the view.
        """
        embed = discord.Embed(
            title='Время истекло - ТОП вайфу был закрыт',
            description='Чтобы еще раз посмотреть рейтинг '
            'вызови команду /top_waifu',
            color=0x334873
        )
        await self.message.edit(embed=embed, view=None)

    async def update_buttons(self, interaction: Interaction) -> None:
        """
        Update the navigation buttons based on the current state.

        Args:
            interaction (Interaction): The interaction event triggered.
        """
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
    async def previous(self, interaction: Interaction, _) -> None:
        """
        Handle the action of going to the previous page.

        Args:
            interaction (Interaction): The interaction event triggered.
            _ (Any): Unused parameter.
        """
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
    async def next(self, interaction: Interaction, _) -> None:
        """
        Handle the action of going to the next page.

        Args:
            interaction (Interaction): The interaction event triggered.
            _ (Any): Unused parameter.
        """
        self._queue.rotate(-1)
        embed = self._queue[0]
        self._current_page += 1
        await self.update_buttons(interaction=interaction)
        await interaction.response.edit_message(embed=embed)

    @property
    def initial(self) -> discord.Embed:
        """
        Get the initial embed for the PaginatorView.

        Returns:
            discord.Embed: The initial embed.
        """
        return self._initial


class UserInteractionCog(commands.Cog):
    """
    A cog for user interaction commands.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the UserInteractionCog.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
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
    ) -> Optional[discord.Role]:
        """
        Check if a role with the given name exists in the guild.

        Args:
            interaction (Interaction): The interaction event triggered.
            role (str): The role name to check.

        Returns:
            Optional[discord.Role]: The role if it exists, else None.
        """
        return discord.utils.get(
            interaction.guild.roles,
            name=role.lower().strip()
        )

    async def get_character(
        self,
        character_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get character data from Shikimori API.

        Args:
            character_id (int): The ID of the character on Shikimori.

        Returns:
            Optional[Dict[str, Any]]: Character data if found, else None.
        """
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
        """
        Create a role for the user and set permissions for channels.

        Args:
            interaction (Interaction): The interaction event triggered.
            role_name (str): The name of the role to create.

        Returns:
            None
        """
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
        """
        Perform necessary checks before granting permission to the user.

        Args:
            interaction (Interaction): The interaction event triggered.
            role (str): The name of the role to be created.
            urls (List[str]): List of Shikimori URLs of waifus.

        Returns:
            None
        """
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

        to_add = []

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
                    to_add.append(waifu_data)

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

        for data in to_add:
            await add_waifu_to_user(
                discord_id=discord_id,
                waifu_data=data
            )

        await self.create_role_and_permission(
            interaction=interaction,
            role_name=role
        )

    async def remove_unused_roles(self) -> None:
        """
        Remove roles that are not assigned to any member in the guild.

        Returns:
            None
        """
        guilds = self.bot.guilds
        for guild in guilds:
            for role in guild.roles:
                if len(role.members) == 0:
                    await role.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        Event handler for when a member joins the server.

        Args:
            member (discord.Member): The member who joined the server.

        Returns:
            None
        """
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
            ),
            suppress_embeds=True
        )

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member: discord.Member,
    ) -> None:
        """
        Event handler for when a member leaves the server.

        Args:
            member (discord.Member): The member who left the server.

        Returns:
            None
        """

        try:
            await self.remove_unused_roles()
        except Forbidden as error:
            logging.exception(error)

        await remove_user_and_userwaifulinks(
            discord_id=member.id
        )

    @app_commands.command(
        name='grant_permission',
        description='Отправить список из 5 вайфу с сайта '
        'shikimori.one для получения доступа в голосовые каналы'
    )
    @app_commands.describe(
        role='Напиши название своей роли, '
        'которую я создам и присвою тебе',
        shikimori_urls='Ссылки на 5 вайфу с сайта '
        'shikimori.one через запятую'
    )
    @user_interaction_check()
    async def grant_permission(
            self,
            interaction: Interaction,
            role: str,
            *,
            shikimori_urls: str) -> None:
        """
        Command to request granting permission to access
        voice channels by submitting a list
        of 5 waifus from the shikimori.one website.

        Args:
            interaction (Interaction): The interaction event triggered.
            role (str): The name of the role that will be created
            and assigned to the user.
            shikimori_urls (str): Links to 5 waifus from shikimori.one,
            separated by commas.

        Returns:
            None
        """
        await interaction.response.defer(ephemeral=True)

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

    @grant_permission.error
    async def grant_permission_error(
        self,
        interaction: Interaction,
        error
    ) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='show_waifus',
        description='Посмотреть своих добавленных вайфу '
        'или вайфу другого пользователя'
    )
    @app_commands.describe(
        user='Никнейм(регистрозависимый!) или юзернейм пользователя, '
        'вайфу которого ты хочешь посмотреть'
    )
    @user_interaction_check()
    async def show_my_waifus(
        self,
        interaction: Interaction,
        user: str = None
    ) -> None:
        """
        Command to display the list of waifus added
        by the user or another user.

        Args:
            interaction (Interaction): The interaction event triggered.
            user (str, optional): Username of the user whose
            waifus are to be displayed.

        Returns:
            None
        """
        await interaction.response.defer()

        bot_names = [
            interaction.guild.me.display_name,
            interaction.guild.me.name
        ]

        if user:
            discord_id = interaction.guild.get_member_named(user)
        else:
            discord_id = interaction.user

        try:
            waifus = await get_user_waifus(discord_id=discord_id.id)
        except AttributeError:
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['user_not_found']
            )
            return

        if not waifus:
            if user in bot_names:
                await interaction.followup.send(
                    USER_INTERACTION_ANSWERS[
                        'show_bot_waifu'
                    ]
                )
                return
            if user:
                await interaction.followup.send(
                    USER_INTERACTION_ANSWERS[
                        'show_other_waifu_err'
                    ].format(username=user)
                )
                return
            await interaction.followup.send(
                USER_INTERACTION_ANSWERS['show_my_waifu_err']
            )
            return

        embed = discord.Embed(
            title=f'Список вайфу {discord_id.global_name}', color=0x334873)

        for number, waifu_link in enumerate(waifus, start=1):
            waifu = waifu_link.waifu
            field_value = (
                f'Ссылка: https://shikimori.one{waifu.url}\n'
                f'Еще известна, как: {waifu.alt_name}\n'
                f'Имя на японском: {waifu.japanese_name}\n'
                f'Shikimori ID: {waifu.shikimori_id}'
            )

            if waifu_link.true_love:
                field_value = (
                    f'`❤️ TRUE LOVE ❤️` '
                    f'Выбрана самой любимой вайфу у '
                    f'{discord_id.global_name}\n{field_value}'
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

    @show_my_waifus.error
    async def show_my_waifus_error(
        self,
        interaction: Interaction,
        error
    ) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='true_love',
        description='Добавить лейбл True Love для одной из твоих вайфу'
    )
    @app_commands.describe(
        waifu_url='Отправь ссылку на ранее добавленную вайфу'
    )
    @user_interaction_check()
    async def true_love(
        self,
        interaction:
        Interaction, waifu_url: str
    ) -> None:
        """
        Command to set the True Love label for a specific waifu.

        Args:
            interaction (Interaction): The interaction event triggered.
            waifu_url (str): URL of the waifu to set as True Love.

        Returns:
            None
        """
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

    @true_love.error
    async def true_love_error(
        self,
        interaction: Interaction,
        error
    ) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='delete_true_love',
        description='Удалить лейбл True Love, установленный '
        'на одной из твоих вайфу'
    )
    @user_interaction_check()
    async def delete_true_love(self, interaction: Interaction) -> None:
        """
        Command to remove the True Love label from a waifu.

        Args:
            interaction (Interaction): The interaction event triggered.

        Returns:
            None
        """
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

    @delete_true_love.error
    async def delete_true_love_error(
        self,
        interaction: Interaction,
        error
    ) -> None:
        await error_handler(interaction, error)

    @app_commands.command(
        name='top_waifu',
        description='Показать рейтинг вайфу по '
        'кол-ву добавлений пользователями'
    )
    @user_interaction_check()
    async def top_waifu(self, interaction: Interaction) -> None:
        """
        Command to display the top waifus
        based on the number of user additions.

        Args:
            interaction (Interaction): The interaction event triggered.

        Returns:
            None
        """
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
                url=f'https://shikimori.one{waifus[0][4]}',
                description=f'Так же известна, '
                f'как: {waifus[0][3]}\n'
                f'Имя на японском: {waifus[0][6]}\n\n', color=0x334873
            )
            embed.set_author(
                name='ТОП вайфу по кол-ву добавлений пользователями')

            for value in waifu_chunk:
                embed.add_field(
                    name=f'**{value[0].upper()}**\n'
                    f'https://shikimori.one{value[4]}',
                    value=f'```Суммарный рейтинг | '
                    f'{value[1] + value[2]}\n\n'
                    f'Кол-во добавлений | '
                    f'{value[1]}\n'
                    f'Кол-во TRUE LOVE  | '
                    f'{value[2]}```\n==============================',
                    inline=False
                )
            embed.set_thumbnail(url=f'https://shikimori.one{waifus[0][5]}')
            embeds.append(embed)

        view = PaginatorView(embeds)
        await interaction.response.send_message(embed=view.initial, view=view)
        view.message = await interaction.original_response()

    @top_waifu.error
    async def top_waifu_error(
        self,
        interaction: Interaction,
        error
    ) -> None:
        await error_handler(interaction, error)
