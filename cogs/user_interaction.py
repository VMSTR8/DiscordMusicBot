import aiohttp

import re

import random

from urllib.parse import urlparse

from typing import Union, List, Dict, Any

from time import sleep

from collections import deque

import discord
from discord import app_commands, Interaction
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

from settings.settings import DISCORD_VOICE_CHANNELS_ID


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
            description='Чтобы снова посмотреть рейтинг '
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

    @discord.ui.button(emoji='⏮')
    async def previous(self, interaction: Interaction, _):
        self._queue.rotate(1)
        embed = self._queue[0]
        self._current_page -= 1
        await self.update_buttons(interaction=interaction)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(emoji='⏭')
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
        return discord.utils.get(interaction.guild.roles, name=role.lower().strip())

    async def is_character_exit(self, character_id: int) -> bool:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://shikimori.one/api/characters/{character_id}"
            ) as response:
                return response.status == 200

    async def fetch_waifu_data(self, character_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://shikimori.one/api/characters/{character_id}"
            ) as response:
                # TODO dataclass
                return await response.json()

    async def create_role_and_permission(
            self,
            interaction: Interaction,
            role_name: str
    ) -> None:
        new_role = await interaction.guild.create_role(
            name=role_name.lower().strip(),
            color=discord.Color(random.randint(0, 0xFFFFFF))
        )

        await interaction.user.add_roles(new_role)

        voice_channels_id = DISCORD_VOICE_CHANNELS_ID.split(',')

        for voice_channel_id in voice_channels_id:
            voice_channel = interaction.guild.get_channel(
                int(voice_channel_id))
            await voice_channel.set_permissions(
                new_role,
                view_channel=True,
                connect=True,
                speak=True
            )

        await interaction.followup.send(
            f'Не то, чтобы мне до тебя было какое-то дело, но...\n'
            f'Я создала роль **{role_name.capitalize()}** для тебя и выдала '
            f'доступы во все голосовые каналы.'
        )

    async def checks_before_grant_permission(
            self,
            interaction: Interaction,
            role: str,
            urls: List[str]
    ) -> None:
        if len(urls) != 5:
            await interaction.followup.send(
                '**Baaaka!** Тебе же было сказано, '
                'отправь 5 ссылок, ни больше ни меньше!',
            )
            return

        valid_urls = []
        for url in urls:
            if re.search(self.shikimore_chars, url):
                valid_urls.append(url)
            else:
                await interaction.followup.send(
                    f'*Надулась*\n\n**{url}**, вот это похоже на '
                    'ссылку на персонажа с сайта Shikimori?',
                )
                return

        if len(valid_urls) != len(set(valid_urls)):
            await interaction.followup.send(
                'Ты всегда так глупо ведешь себя, '
                'или только передо мной? Твои вайфу должны быть '
                'уникальны! А ты добавляешь одну и ту же вайфу несколько раз...'
            )
            return

        for url in valid_urls:
            character_id = re.search(self.shikimore_chars, url).group(2)
            character_id = re.sub(r'\D', '', character_id)

            discord_id = interaction.user.id
            try:
                character_exists = await self.is_character_exit(
                    character_id=character_id
                )
            except Exception as error:
                await interaction.followup.send(
                    'Что-то пошло не так :( Извини... я все напортачила. '
                    'Надеюсь, ты не сердишься на меня... Попробуй еще раз!'
                )
                print(error)
            if not character_exists:
                await interaction.followup.send(
                    f'Персонаж по ссылке {url} не найден на Shikimori. '
                    'Повтори команду, введя корректные ссылки!',
                )
                return

            sleep(0.1)
            waifu_data = await self.fetch_waifu_data(
                character_id=character_id
            )
            await add_waifu_to_user(
                discord_id=discord_id,
                waifu_data=waifu_data
            )

        await self.create_role_and_permission(
            interaction=interaction,
            role_name=role
        )

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
                '*Я случайно заметила, как ты уже отправлял список своих вайфу... '
                'Но это только потому что мне было скучно, '
                'а не потому что мне важно, понял?!'
            )
            return

        existing_role = await self.is_role_exist(
            interaction=interaction,
            role=role
        )
        if existing_role:
            await interaction.followup.send(
                f'Роль **{role}** уже существует на сервере!',
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
    async def show_user_waifus(self, interaction: Interaction):
        await interaction.response.defer()

        discord_id = interaction.user.id
        username = interaction.user.display_name

        waifus = await get_user_waifus(discord_id=discord_id)
        if not waifus:
            await interaction.followup.send(
                'Ты еще не заполнял список своих вайфу\n'
                'Вызови команду /grant_permission для заполнения списка'
            )

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
            text='Ты можешь добавить лейбл True Love вызовом команды /true_love'
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
                'Ой, какой сюрприз! Ты до сих пор не получил '
                'права на сервере. Наверное, так и будешь вечным молчуном...',
                ephemeral=True
            )
            return

        if not waifu:
            await interaction.response.send_message(
                'Все уже давно добавили вайфу, а ты, как всегда, '
                'остаешься в прошлом. Ты ведь хоть знаешь, '
                'что такое "вайфу"? А то вместо правильной '
                'ссылки ты скинул мне какую-то ерунду...',
                ephemeral=True
            )
            return

        user_waifu_connection = await check_user_waifu_connection(
            user=user,
            waifu=waifu
        )
        if not user_waifu_connection:
            await interaction.response.send_message(
                'А ты всё так набиваешь оскомину своими запросами! '
                'Нет, конечно же, между указанной вайфу и тобой нет '
                'никакой связи. Но раз ты так недоумеваешь, '
                'мне просто интересно понаблюдать за твоей неудачной '
                'попыткой. Но, знаешь ли, дело твоё – '
                'что там у тебя в голове.',
                ephemeral=True
            )
            return

        await set_true_love(user=user, waifu=waifu)
        await interaction.response.send_message(
            f'Ах, наконец-то ты сделал хоть какой-то шаг вперёд! '
            f'`❤️ TRUE LOVE ❤️` для **{waifu.waifu_name_rus}** добавлен, '
            f'но, конечно же, это вовсе не значит, что я впечатлена или '
            f'что-то подобное. Ты просто делаешь то, что должен был сделать.',
            ephemeral=True
        )

    @app_commands.command(
        name='delete_true_love',
        description='Удалить лейбл True Love, установленный на одной из твоих вайфу'
    )
    async def delete_true_love(self, interaction: Interaction):
        discord_id = interaction.user.id
        user = await get_user(discord_id=discord_id)

        if not user:
            await interaction.response.send_message(
                'Пфф, ну и что ты тут пытаешься бросить кого-то, '
                'когда еще даже не получил права на сервере?',
                ephemeral=True
            )
            return

        await remove_true_love(user=user)
        await interaction.response.send_message(
            f'*Смотрит на тебя с отвращением*\n\nВзял и решил '
            f'бросить кого-то — типичное поведение для таких, как ты.',
            ephemeral=True
        )

    @app_commands.command(
        name='top_waifu',
        description='Показать рейтинг вайфу по кол-ву добавлений пользователями'
    )
    async def waifu_top(self, interaction: Interaction):
        waifus = await count_waifus()
        string_to_add = ['🥇', '🥈', '🥉']

        if not waifus:
            await interaction.response.send_message(
                'Знаешь, я, конечно, не сильно в этом заинтересована, '
                'но, кажется, ты пытаешься посмотреть ТОП вайфу. '
                'Но как-то все пошло не по плану. Скорее всего никто '
                'еще не добавлял себе вайфу при помощи команды '
                '/grant_premission. Но это, наверное, '
                'не стоит мне беспокоиться...',
                ephemeral=True
            )

        if len(waifus) >= len(string_to_add):
            for i in range(len(string_to_add)):
                waifus[i][0] = f'{string_to_add[i]} {waifus[i][0]}'

        embeds = []
        for waifu_chunk in discord.utils.as_chunks(waifus, 10):
            filtered_title = re.sub(r'[^\w\s\d]', '', waifus[0][0])
            embed = discord.Embed(
                title=f'Самая популярная вайфу сервера:\n{filtered_title.strip()}',
                url=f'https://shikimori.me{waifus[0][3]}',
                description=f'Так же известна, как: {waifus[0][2]}\n'
                f'Имя на японском: {waifus[0][5]}\n\n', color=0x334873
            )
            embed.set_author(
                name='ТОП вайфу по кол-ву добавлений пользователями')

            for value in waifu_chunk:
                embed.add_field(
                    name=f'**{value[0]}**',
                    value=f'`Кол-во добавлений: {value[1]}`\n==========',
                    inline=False
                )
            embed.set_thumbnail(url=f'https://shikimori.me{waifus[0][4]}')
            embeds.append(embed)

        view = PaginatorView(embeds)
        await interaction.response.send_message(embed=view.initial, view=view)
        view.message = await interaction.original_response()
