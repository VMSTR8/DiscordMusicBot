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

from cogs.answers import (
    USER_INTERACTION_ANSWERS,
    WAIFU_RESPONSE
)


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
            color=0x9966cc
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


class ServerUsers(discord.ui.UserSelect):
    """
    A custom user selection menu for selecting users from the server.

    Methods:
        show_bots_waifu(interaction: Interaction):
        Generates a list of the chatbot's "waifus".
        callback(interaction: Interaction): Handles the interaction
        when a user is selected.
    """

    def __init__(self):
        """
        Initialize the ServerUsers user selection menu.
        """

        super().__init__(
            placeholder='Выбери пользователя...',
            min_values=1,
            max_values=1
        )

    async def show_bots_waifu(
            self,
            interaction: Interaction,
    ) -> None:
        """
        The function generates a list of the chatbot's "waifus",
        consisting of the user who invoked the function
        and up to 4 random users who already have roles
        assigned on the server.

        Args:
            interaction (Interaction): The interaction event triggered.

        Returns:
            None
        """
        invoking_user = interaction.user
        random_response = random.sample(WAIFU_RESPONSE, 4)

        all_guild_users = [
            user for user in interaction.guild.members
            if not user.bot
            and any(role != user.guild.default_role for role in user.roles)
            and user.id != invoking_user.id
        ]

        if len(all_guild_users) > 4:
            selected_guild_users = random.sample(all_guild_users, 4)
        else:
            selected_guild_users = all_guild_users

        user_and_response = dict(
            zip(selected_guild_users, random_response)
        )

        embed = discord.Embed(
            title=f'Так, вот мой список вайфу',
            color=0x9966cc
        )
        embed.add_field(
            name=f'1. Имя пользователя: {invoking_user.global_name}',
            value=(
                f'Имя пользователя на сервере: '
                f'**{invoking_user.display_name}**\n'
                f'`❤️ TRUE LOVE ❤️` - '
                f'**{interaction.guild.me.display_name}** '
                f'неровно дышит к данному пользователю!\n'
                f'||ЧТО??? И ЗАЧЕМ ПОЛЬЗОВАТЕЛЮ ОБ ЭТОМ ЗНАТЬ?\n'
                f'*Надулась и покраснела*||'
            ),
            inline=False
        )

        for number, (user, response) in enumerate(
            user_and_response.items(),
            start=2
        ):
            embed.add_field(
                name=(
                    f'{number}. Имя пользователя: '
                    f'{user.global_name}'
                ),
                value=(
                    f'Имя пользователя на сервере: '
                    f'**{user.display_name}**\n'
                    f'*{response}*'
                ),
                inline=False
            )
        embed.set_thumbnail(
            url=invoking_user.display_avatar
        )
        embed.set_footer(
            text='Хватит уже смотреть на мой список!\n'
            'Лучше посмотри на вайфу других пользователей '
            'вызовом команды /show_waifus'
        )

        await interaction.response.send_message(
            embed=embed,
        )

    async def callback(
            self,
            interaction: Interaction
    ) -> None:
        """
        Handle the interaction when a user is selected from the menu.

        Args:
            interaction (Interaction): The interaction event triggered.

        Returns:
            None
        """
        selected_user = self.values[0]

        waifus = await get_user_waifus(discord_id=selected_user.id)

        if not waifus:
            if (selected_user.bot
                    and selected_user.id == interaction.message.author.id):
                await self.show_bots_waifu(
                    interaction=interaction
                )
                return
            if selected_user.bot:
                await interaction.response.send_message(
                    USER_INTERACTION_ANSWERS[
                        'show_another_bot_err'
                    ],
                )
                return
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'show_other_waifu_err'
                ].format(username=selected_user.global_name),
            )
            return

        embed = discord.Embed(
            title=f'Список вайфу пользователя '
            f'{selected_user.display_name}',
            color=0x9966cc
        )

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
                    f'{selected_user.global_name}\n{field_value}'
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

        await interaction.response.send_message(
            embed=embed,
        )


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

        character_id_unique = [
            re.search(self.shikimore_chars, url).group(2)
            for url in valid_urls
        ]
        if len(character_id_unique) != len(set(character_id_unique)):
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
        description='Отправить 5 ссылок на вайфу с сайта '
        'shikimori.one для получения доступа в голосовые каналы'
    )
    @app_commands.describe(
        role='Напиши название своей роли, '
        'которую я создам и присвою тебе',
        first_url='Ссылка на 1-ю вайфу c https://shikimori.one/characters',
        second_url='Ссылка на 2-ю вайфу c https://shikimori.one/characters',
        third_url='Ссылка на 3-ю вайфу c https://shikimori.one/characters',
        fourth_url='Ссылка на 4-ю вайфу c https://shikimori.one/characters',
        fifth_url='Ссылка на 5-ю вайфу c https://shikimori.one/characters'
    )
    @app_commands.rename(
        role='название_роли',
        first_url='первая_вайфу',
        second_url='вторая_вайфу',
        third_url='третья_вайфу',
        fourth_url='четвертая_вайфу',
        fifth_url='пятая_вайфу'
    )
    @commands.guild_only()
    async def grant_permission(
            self,
            interaction: Interaction,
            role: str,
            *,
            first_url: str,
            second_url: str,
            third_url: str,
            fourth_url: str,
            fifth_url: str
    ) -> None:
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

        urls = [
            url.strip() for url in [
                first_url,
                second_url,
                third_url,
                fourth_url,
                fifth_url
            ]
        ]
        await self.checks_before_grant_permission(
            interaction=interaction,
            role=role,
            urls=urls
        )

    @app_commands.command(
        name='show_waifus',
        description='Посмотреть список добавленных вайфу '
        'пользователя'
    )
    @commands.guild_only()
    async def show_waifus(
        self,
        interaction: Interaction,
    ) -> None:
        """
        This method creates a selection menu for users
        to choose a server member and view their list of waifus.
        The selection menu is added to a view
        and sent as a response to the interaction.

        Args:
            interaction (Interaction): The interaction event triggered.

        Returns:
            None
        """
        select = ServerUsers()
        view = discord.ui.View()

        view.add_item(select)

        await interaction.response.send_message(
            'Выбери пользователя, вайфу которого ты хочешь посмотреть',
            view=view,
            ephemeral=True,
        )

    @app_commands.command(
        name='true_love',
        description='Добавить лейбл True Love для одной из твоих вайфу'
    )
    @app_commands.describe(
        waifu_url='Отправь ссылку на ранее добавленную вайфу'
    )
    @commands.guild_only()
    async def true_love(
        self,
        interaction: Interaction,
        waifu_url: str
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

    @app_commands.command(
        name='delete_true_love',
        description='Удалить лейбл True Love, установленный '
        'на одной из твоих вайфу'
    )
    @commands.guild_only()
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

    @app_commands.command(
        name='top_waifu',
        description='Показать рейтинг вайфу по '
        'кол-ву добавлений пользователями'
    )
    @commands.guild_only()
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
                f'Имя на японском: {waifus[0][6]}\n\n', color=0x9966cc
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

    @app_commands.command(
        name='change_role_color',
        description='Изменить цвет  '
        'своей роли'
    )
    @app_commands.describe(
        role_name='Подтверди смену цвета, '
        'написав сюда название своей роли',
        color='Напиши сюда HEX код цвета, '
        'например: #9966CC'
    )
    @app_commands.rename(
        role_name='название_роли',
        color='цвет_роли'
    )
    @commands.guild_only()
    async def change_role_color(
        self,
        interaction: Interaction,
        role_name: str,
        color: str
    ) -> None:
        """
        Command to change the color of a user's role.

        Args:
            interaction (Interaction): The interaction event triggered.
            role_name (str): The name of the role to change the color.
            color (str): The HEX color code to apply.

        Returns:
            None
        """

        role_name = role_name.lower().strip()
        guild_role = discord.utils.get(
            interaction.guild.roles,
            name=role_name
        )

        if guild_role is None:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'role_not_found'
                ].format(role_name=role_name.capitalize()),
                ephemeral=True
            )
            return

        if guild_role not in interaction.user.roles:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'role_not_assigned'
                ].format(role_name=role_name.capitalize()),
                ephemeral=True
            )
            return

        if not re.match(
            r'^#(?:[0-9a-fA-F]{3}){1,2}$',
            color
        ):
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'invalid_hex_code'
                ],
                ephemeral=True
            )
            return

        try:
            hex_color = int(color.lstrip('#'), 16)
            await guild_role.edit(
                color=discord.Color(hex_color)
            )
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'color_changed'
                ].format(
                    role_name=role_name.capitalize(),
                    color=color.upper()
                ),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'permission_error'
                ],
                ephemeral=True
            )
        except Exception as error:
            logging.exception(error)
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'unexpected_error'
                ],
                ephemeral=True
            )

    @app_commands.command(
        name='change_role_name',
        description='Изменить название '
        'своей роли'
    )
    @app_commands.describe(
        old_role_name='Подтверди изменение, '
        'написав сюда название своей роли',
        new_role_name='Напиши сюда новое название '
        'своей роли'
    )
    @app_commands.rename(
        old_role_name='текущее_название_роли',
        new_role_name='новое_название_роли'
    )
    @commands.guild_only()
    async def change_role_name(
        self,
        interaction: Interaction,
        old_role_name: str,
        new_role_name: str
    ) -> None:
        """
        Command to change the name of a user's role.

        Args:
            interaction (Interaction): The interaction event triggered.
            old_role_name (str): The current name of the role.
            new_role_name (str): The new name for the role.

        Returns:
            None
        """

        old_role_name = old_role_name.lower().strip()
        new_role_name = new_role_name.lower().strip()
        guild_role = discord.utils.get(
            interaction.guild.roles,
            name=old_role_name
        )

        if guild_role is None:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'role_not_found'
                ].format(role_name=old_role_name.capitalize()),
                ephemeral=True
            )
            return

        if guild_role not in interaction.user.roles:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'role_not_assigned'
                ].format(role_name=old_role_name.capitalize()),
                ephemeral=True
            )
            return

        if old_role_name == new_role_name:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'same_role_name'
                ].format(role_name=old_role_name.capitalize()),
                ephemeral=True
            )
            return

        if await self.is_role_exist(
            interaction=interaction,
            role=new_role_name
        ):
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'role_already_exists'
                ].format(role=new_role_name.capitalize()),
                ephemeral=True
            )
            return

        try:
            await guild_role.edit(name=new_role_name)
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'name_changed'
                ].format(
                    old_role_name=old_role_name.capitalize(),
                    new_role_name=new_role_name.capitalize()
                ),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'permission_error'
                ],
                ephemeral=True
            )
        except Exception as error:
            logging.exception(error)
            await interaction.response.send_message(
                USER_INTERACTION_ANSWERS[
                    'unexpected_error'
                ],
                ephemeral=True
            )
