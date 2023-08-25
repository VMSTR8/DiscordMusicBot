from tortoise import Tortoise, run_async

from database import config


async def init() -> None:
    '''
    Initializes Tortoise ORM and generates database schemas.

    Note:
        This function initializes Tortoise ORM
        with the provided database URL and modules,
        and generates the database schemas.

    Raises:
        tortoise.exceptions.ConfigurationError:
        If there's a configuration error.
    '''
    await Tortoise.init(
        db_url=config.DATABASE_URL,
        modules={'models': ['database.user.models', 'aerich.models']}
    )

    await Tortoise.generate_schemas()

if __name__ == '__main__':
    '''
    Entry point for initializing the database and generating schemas.
    '''
    run_async(init())
