from typing import Dict, Any, Optional, List

from database.user.models import User, Waifu, UserWaifuLink


async def add_waifu_to_user(
        discord_id: int,
        waifu_data: Dict[str, Any]
) -> None:
    """
    Adds a waifu to a user's collection.

    Args:
        discord_id (int): Discord ID of the user.
        waifu_data (Dict[str, Any]): Data of the waifu to be added.

    Note:
        If the waifu already exists, creates
        a UserWaifuLink for the user and existing waifu.
        If the waifu doesn't exist, creates a new waifu and UserWaifuLink.
    """
    user, _ = await User.get_or_create(discord_id=discord_id)

    waifu_id = waifu_data['id']
    existing_waifu = await Waifu.filter(shikimori_id=str(waifu_id)).first()

    if existing_waifu:
        await UserWaifuLink.create(
            user_id=user.id,
            waifu_id=existing_waifu.id,
            is_true_love_set=False
        )
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

        await UserWaifuLink.create(
            user_id=user.id,
            waifu_id=waifu.id,
            is_true_love_set=False
        )


async def check_user_waifu_link_exists(discord_id: int) -> Optional[bool]:
    """
    Checks if a user-waifu link exists for a given user.

    Args:
        discord_id (int): Discord ID of the user.

    Returns:
        Optional[bool]: True if a link exists,
        False if not, None if user doesn't exist.
    """
    user = await User.filter(discord_id=discord_id).first()
    if user:
        return await UserWaifuLink.filter(user_id=user.id).exists()
    else:
        return None


async def get_user_waifus(discord_id: int) -> Optional[List[UserWaifuLink]]:
    """
    Gets a list of waifus associated with a user.

    Args:
        discord_id (int): Discord ID of the user.

    Returns:
        Optional[List[UserWaifuLink]]: List of UserWaifuLink
        instances if waifus found, None if not.
    """
    user = await User.get_or_none(discord_id=discord_id)
    if not user:
        return None

    waifus = await UserWaifuLink.filter(
        user_id=user.id
    ).prefetch_related('waifu').all()
    if not waifus:
        return None

    return waifus


async def get_user(discord_id: int) -> Optional[User]:
    """
    Gets a User instance by Discord ID.

    Args:
        discord_id (int): Discord ID of the user.

    Returns:
        Optional[User]: User instance if found, None if not.
    """
    return await User.get_or_none(discord_id=discord_id)


async def get_waifu_by_url(waifu_url: str) -> Optional[Waifu]:
    """
    Gets a Waifu instance by URL.

    Args:
        waifu_url (str): URL of the waifu's page.

    Returns:
        Optional[Waifu]: Waifu instance if found, None if not.
    """
    return await Waifu.filter(url=waifu_url).first()


async def check_user_waifu_connection(
        user: User,
        waifu: Waifu
) -> Optional[UserWaifuLink]:
    """
    Checks if a connection exists between a user and a waifu.

    Args:
        user (User): User instance.
        waifu (Waifu): Waifu instance.

    Returns:
        Optional[UserWaifuLink]: UserWaifuLink instance
        if connection exists, None if not.
    """
    return await UserWaifuLink.get_or_none(user=user.id, waifu=waifu.id)


async def set_true_love(user: User, waifu: Waifu) -> None:
    """
    Sets the "true love" status between a user and a waifu.

    Args:
        user (User): User instance.
        waifu (Waifu): Waifu instance.
    """
    await UserWaifuLink.filter(user=user.id).update(true_love=False)
    await UserWaifuLink.filter(
        user=user.id,
        waifu=waifu.id
    ).update(true_love=True)


async def remove_true_love(user: User) -> None:
    """
    Removes the "true love" status for a user.

    Args:
        user (User): User instance.
    """
    await UserWaifuLink.filter(user=user.id).update(true_love=False)


async def count_waifus() -> Optional[List[List[Any]]]:
    """
    Counts the number of users associated with each waifu.

    Returns:
        Optional[List[List[Any]]]: A list of waifu information
        with user counts if waifus found, None if not.
    """
    waifus = await Waifu.all()
    if not waifus:
        return None

    waifu_counts = [
        [
            waifu.waifu_name_rus,
            await UserWaifuLink.filter(waifu=waifu).count(),
            await UserWaifuLink.filter(waifu=waifu, true_love=True).count(),
            waifu.alt_name,
            waifu.url,
            waifu.image,
            waifu.japanese_name
        ]
        for waifu in waifus
    ]

    sorted_waifu_counts = sorted(
        waifu_counts, key=lambda x: x[1] + x[2], reverse=True)

    if not sorted_waifu_counts:
        return None

    return sorted_waifu_counts


async def remove_user_and_userwaifulinks(discord_id: int) -> None:
    """
    Removes a user and all associated user-waifu links.

    Args:
        discord_id (int): Discord ID of the user.
    """
    user = await User.get_or_none(discord_id=discord_id)

    if user:
        await UserWaifuLink.filter(user_id=user.id).delete()
        await user.delete()
