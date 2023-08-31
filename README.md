# Мультифункциональный чат-бот для Discord

> This project is being developed in Russian language without English or any other language localization. If you are interested in adding English or other language localization, please contact me through the contacts provided in the profile.

Чат-бот, который умеет воспроизводить музыку, а так же работает с пользователями при входе участника на сервер. Умеет "регистрировать" на сервере, выдвая права в заданные голосовые каналы. Так как бот создается "тем еще виабушником" для использования на довольно небольшом сервере дискорда, поэтому основной функционал работы с пользователями построен на аниме-тематике.

Стэк: [Python 3.10.8](https://www.python.org/doc/), [Discord.py 2.3.2](https://discordpy.readthedocs.io/en/stable/), [Wavelink 2.6.4](https://wavelink.dev/en/latest/), [Tortoise ORM 0.19.3](https://tortoise.github.io/index.html) [*(tutel!)*](https://youtu.be/oxzEdm29JLw), [Lavalink 3.7.8](https://github.com/lavalink-devs/Lavalink)

## Важная информация
* Бот не предназначен для добавления более чем на одном сервер дискорда, ибо я писал его исключительно под свой единственный серер. Разворачиваете бота у себя? Помните: один развернутый бот на один сервер.
* Допустим, вам нужен просто музыкальный чат-бот. Ненужные команды можно отключить прямиком у вас на сервере в разделе настройки сервере->интеграция->выбрать бота и нажать "управление". 
* Вопросы и предложения по боту можно направлять сюда: https://discord.gg/hk4QRyVXEY

## Как развернуть бота у себя
Создайте `docker-compose.yml` со следующим содержимым (не забудьте заменить переменные):
```yaml
version: "3.8"

services:
    lavalink:
        image: fredboat/lavalink:3.7.8
        container_name: lavalink
        restart: unless-stopped
        environment:
            - _JAVA_OPTIONS=-Xmx6G
            - SERVER_PORT=2333
            - SERVER_ADDRESS=0.0.0.0
            - LAVALINK_SERVER_PASSWORD=<придуманный_вами_пароль>
            - LAVALINK_SERVER_SOURCES_HTTP=true
        networks:
            - lavalink
        expose:
            - 2333
        ports:
            - 2333:2333

    discordbot:
        image: vmstr8/discord-music-bot:<версия_бота>
        container_name: discordbot
        restart: unless-stopped
        depends_on:
            - lavalink
        networks:
        - lavalink
        volumes:
        - ./data/:/discordbot/data/
        - ./entrypoint.sh:/discordbot/entrypoint.sh
        environment:
            - BOT_TOKEN=<токен_дискорд_бота>
            - WAVELINK_URI=http://lavalink:2333
            - WAVELINK_PASSWORD=<придуманный_вами_пароль_из_блока_lavalink>
            - DATABASE_URL=sqlite://data/db.sqlite3
            - DISCORD_TEXT_CATEGORIES_ID=<каким_текстовым_категориям_выдавать_разрешение_через_запятую>
            - MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID=<в_каких_каналах_удалять_собщения_пользователей>
            - GREETINGS_CHANNEL=<канал_для_приветственных_сообщеий_бота>
            - DISCORD_VOICE_CATEGORIES_ID=<каким_голосовым_категориям_выдавать_разрешение_через_запятую>

networks:
    lavalink:
        name: lavalink
```

Пример `DISCORD_TEXT_CATEGORIES_ID` и `DISCORD_VOICE_CATEGORIES_ID`: `01234567890123456789,9876543210987654321`

Можно вписать любое кол-во категорий. Если вам не нужно удалять сообщения в чате, где используются бот-команды, то в `MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID` просто ставьте 0.

Версии чат-бота можно найти [по ссылке](https://hub.docker.com/repository/docker/vmstr8/discord-music-bot/general) (tags это и есть версии).

После создания файла пропишите в консоле команду `docker-compose up -d`. Бот должен запуститься. Смотрите [Docker Compose Up](https://github.com/lavalink-devs/Lavalink#:~:text=d.%20See-,Docker%20Compose%20Up,-If%20your%20bot).