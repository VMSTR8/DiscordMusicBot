import aiohttp

import re

import random

from typing import Union, List, Dict, Any

from time import sleep

import discord
from discord import app_commands, Interaction
from discord.ext import commands

from database.user.db_handler import (
    add_waifu_to_user,
    check_user_waifu_link_exists
)

from settings.settings import DISCORD_VOICE_CHANNELS_ID


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

    async def create_role_and_permission(self, interaction: Interaction, role_name: str) -> None:
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
                '*Кхм*, ну... не то, чтобы меня это волнует, но ты '
                'уже аполнил список своих вайфу... и ладно, не думай, '
                'что я о чем-то беспокоюсь, дурак!'
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
