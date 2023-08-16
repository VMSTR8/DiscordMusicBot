from typing import Dict, Any, Optional

from database.user.models import User, Waifu, UserWaifuLink

async def add_waifu_to_user(discord_id: int, waifu_data: Dict[str, Any]) -> None:
    user, _ = await User.get_or_create(discord_id=discord_id)

    waifu_id = waifu_data['id']
    existing_waifu = await Waifu.filter(shikimori_id=str(waifu_id)).first()

    if existing_waifu:
        await UserWaifuLink.create(user_id=user.id, waifu_id=existing_waifu.id)
    else:
        waifu = await Waifu.create(
            shikimori_id = waifu_id,
            waifu_name = waifu_data['name'],
            waifu_name_rus = waifu_data['russian'],
            image = waifu_data['image']['x96'],
            url = waifu_data['url'],
            alt_name = waifu_data['altname'],
            japanese_name = waifu_data['japanese']
        )

        await UserWaifuLink.create(user_id=user.id, waifu_id=waifu.id)

async def check_user_waifu_link_exists(discord_id: int) -> Optional[bool]:
    user = await User.filter(discord_id=discord_id).first()
    if user:
        return await UserWaifuLink.filter(user_id=user.id).exists()
    else:
        return None
    