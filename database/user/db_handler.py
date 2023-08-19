from typing import Dict, Any, Optional

from database.user.models import User, Waifu, UserWaifuLink


async def add_waifu_to_user(discord_id: int, waifu_data: Dict[str, Any]) -> None:
    user, _ = await User.get_or_create(discord_id=discord_id)

    waifu_id = waifu_data['id']
    existing_waifu = await Waifu.filter(shikimori_id=str(waifu_id)).first()

    if existing_waifu:
        await UserWaifuLink.create(user_id=user.id, waifu_id=existing_waifu.id, is_true_love_set=False)
    else:
        waifu = await Waifu.create(
            shikimori_id=waifu_id,
            waifu_name=waifu_data['name'],
            waifu_name_rus=waifu_data['russian'],
            image=waifu_data['image']['x96'],
            url=waifu_data['url'],
            alt_name=waifu_data['altname'],
            japanese_name=waifu_data['japanese']
        )

        await UserWaifuLink.create(user_id=user.id, waifu_id=waifu.id, is_true_love_set=False)


async def check_user_waifu_link_exists(discord_id: int) -> Optional[bool]:
    user = await User.filter(discord_id=discord_id).first()
    if user:
        return await UserWaifuLink.filter(user_id=user.id).exists()
    else:
        return None


async def get_user_waifus(discord_id: int):
    user = await User.get_or_none(discord_id=discord_id)
    if not user:
        return None

    waifus = await UserWaifuLink.filter(user_id=user.id).prefetch_related('waifu').all()
    if not waifus:
        return None

    return waifus


async def get_user(discord_id: int):
    return await User.get_or_none(discord_id=discord_id)


async def get_waifu_by_url(waifu_url: str):
    return await Waifu.filter(url=waifu_url).first()


async def check_user_waifu_connection(user: User, waifu: Waifu):
    return await UserWaifuLink.get_or_none(user=user.id, waifu=waifu.id)


async def set_true_love(user: User, waifu: Waifu):
    await UserWaifuLink.filter(user=user.id).update(true_love=False)
    await UserWaifuLink.filter(user=user.id, waifu=waifu.id).update(true_love=True)


async def remove_true_love(user: User):
    await UserWaifuLink.filter(user=user.id).update(true_love=False)


async def count_waifus():

    waifus = await Waifu.all()
    if not waifus:
        return None

    waifu_counts = [
        [
            waifu.waifu_name_rus,
            await UserWaifuLink.filter(waifu=waifu).count(),
            waifu.alt_name,
            waifu.url,
            waifu.image,
            waifu.japanese_name
        ]
        for waifu in waifus
    ]

    sorted_waifu_counts = sorted(
        waifu_counts, key=lambda x: x[1], reverse=True)

    if not sorted_waifu_counts:
        return None

    return sorted_waifu_counts
