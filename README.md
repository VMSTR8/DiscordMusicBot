# Мультифункциональный чат-бот для Discord

> This project is being developed in Russian language without English or any other language localization. If you are interested in adding English or other language localization, please contact me through the contacts provided in the profile.

Чат-бот, который умеет воспроизводить музыку, а так же работает с пользователями при входе участника на сервер. Умеет "регистрировать" на сервере, выдвая права в заданные голосовые каналы. Так как бот создается "тем еще виабушником" для использования на довольно небольшом сервере дискорда, поэтому основной функционал работы с пользователями построен на аниме-тематике.

Стэк: [Python 3.10.8](https://www.python.org/doc/), [Discord.py 2.4.0](https://discordpy.readthedocs.io/en/stable/), [Wavelink 3.4.0](https://wavelink.dev/en/latest/), [Tortoise ORM 0.22.0](https://tortoise.github.io/index.html) [*(tutel!)*](https://youtu.be/oxzEdm29JLw), [Lavalink 4.0.8](https://github.com/lavalink-devs/Lavalink)

## ОБРАТИТЬ ВНИМАНИЕ: О переходе с Youtube на Yandex Music

**TL;DR**

**С Youtube музыка больше не воспроизводится, чинить каждую неделю откровенно надоело, поэтому отныне бот работает через Яндекс Музыку.**

Подробнее:
Примерно с августа - сентября 2024 года youtube активно закручивает гайки в своем сервисе, повышает безопастность, меняет какие-то внутренние алгоритмы и все в таком духе. Я находил информацию, что это делается ради борьбы с блокировщиками рекламы в первую очередь, да и в целом для "улучшения" сервиса. Вот только эти "улучшения" накидали тонну проблем для создателей музыкальных ботов. Yotube просто не дает воспроизвести музыку. Если клиент не авторизован, выдается что-то в духе "подтверди, что ты не бот и зайди на свой аккаунт". Было несколько методов, которые позволяют этот алерт обойти, но каждый из них то и дело отваливается/ломается/требует слишком повышенного внимания.

Вот чтобы больше не заниматься ремонтом постоянно отваливающегося функционала я принял решение перенести музыкальный функционал бота с Youtube на Яндекс Музыку. Все работает точно так же, как и работало, вводите команду /play название_трека и бот ищет музыку, заходит в голосовой канал и воспроизводит найденное. Можно кинуть ссылку на трек с Я.Музыки, тоже сработает. Так же поддерживаются ссылки с Soundcloud и Bandcamp. Но текстовый поиск идет исключительно через Я.Музыку.

Какие есть нюансы, о которых я еще раз упомяну ниже, но и тут на всякий случай напишу. Яндекс музыка требует от вас токен, который получается весьма специфичным образом (нужно успеть скопировать ссылку при авторизации в сервисе, токен будет находится именно в ней). Помимо этого токен живет ровно 1 год с момента его генерации при авторизации, это нужно помнить.

Второй нюанс - если ваш сервер с ботом будет находиться не на территории России или стран СНГ, то на аккаунте, с которого будете получать токен, должна быть оформлена подписка плюс.

Более подробная инструкция по настройки `application.yml` ниже.


## Важная информация
* Бот не предназначен для добавления более чем на одном сервер дискорда, ибо я писал его исключительно под свой единственный серер. Разворачиваете бота у себя? Помните: один развернутый бот на один сервер.
* Допустим, вам нужен просто музыкальный чат-бот. Ненужные команды можно отключить прямиком у вас на сервере в разделе Настройки сервера->Интеграция->выбрать бота и нажать "Управление". 
* Вопросы и предложения по боту можно направлять сюда: https://discord.gg/hk4QRyVXEY

## Как развернуть бота у себя
Создайте `docker-compose.yml` со следующим содержимым (не забудьте заменить переменные).

Пример файла можете [посмотреть тут](./docker-compose_example.yml):
```yaml
services:
    lavalink:
        image: fredboat/lavalink:4.0.8
        container_name: lavalink
        restart: unless-stopped
        environment:
            - _JAVA_OPTIONS=-Xmx6G
            - SERVER_PORT=2333
            - SERVER_ADDRESS=0.0.0.0
            - LAVALINK_SERVER_PASSWORD=<придуманный_вами_пароль>
            - LAVALINK_SERVER_SOURCES_HTTP=true
        volumes:
        - ./application.yml:/opt/Lavalink/application.yml
        networks:
            - lavalink
        expose:
            - 2333
        ports:
            - 2333:2333

    discordbot:
        image: vmstr8/discord-music-bot:<версия_бота_или_просто_напиши_тут_latest>
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
Пример `DISCORD_TEXT_CATEGORIES_ID` и `DISCORD_VOICE_CATEGORIES_ID`: `01234567890123456789,9876543210987654321`. ID каналов получаете нажатием ПКМ по каналу и там будет кнопка "Копировать ID канала".
```yaml
environment:
  - DISCORD_TEXT_CATEGORIES_ID=01234567890123456789,9876543210987654321
  - DISCORD_VOICE_CATEGORIES_ID=01234567890123456789,9876543210987654321
```

Можно вписать любое кол-во категорий. Если вам не нужно удалять сообщения в чате, где используются бот-команды, то в `MESSAGE_NOT_ALLOWED_TEXT_CHANNELS_ID` просто ставьте 0.

Теперь создайте файл `application.yml`, он необходим для настроек Lavalink плагинов. Пример файла так же можете [посмотреть тут](./application_example.yml).
```yaml
plugins:
  lavasrc:
    providers:
      - "ymrec:\"%ISRC%\""
      - "ymsearch:%QUERY%"
    sources:
      youtube: false
      yandexmusic: true
    yandexmusic:
      accessToken: "токен_яндекс_музыки"
      playlistLoadLimit: 1
      albumLoadLimit: 1
      artistLoadLimit: 1

server:
  port: 2333
  address: localhost
lavalink:
  plugins:
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.3.0"
      snapshot: false
  server:
    password: "пароль_вашего_лавалинка"
    sources:
      youtube: false
      soundcloud: true
      bandcamp: true
      twitch: false
      vimeo: false
      mixer: false
      http: true
  pluginsPath: ./plugins

```
С осени 2024 года Youtube вставляет палки в колеса и воспроизведение музыки постоянно ломается. Чтобы не чинить это дело каждую неделю и не ждать фиксов, функционал воспроизведение музыки переведен на сервис Яндекс Музыка. Для работы с Я.Музыкой понадобится плагин [LavaScr](https://github.com/topi314/LavaSrc). Он автоматически установится в папку plugins при развертывании образа в докере. Ну или скачайте плагин и положите в папку самостоятельно, если поднимаете бота локально на своем компьютере.

Чтобы подключить Я.Музыку, вам потребуется токен. Как его получить вы можете прочитать [тут](https://github.com/topi314/LavaSrc?tab=readme-ov-file#yandex-music).

Если вы разворачиваете бота на сервере, который находится за пределами России и некоторых стран СНГ (список есть [здесь](https://github.com/topi314/LavaSrc?tab=readme-ov-file#yandex-music)), то вам потребуется активная подписка "Яндекс Плюс".

Версии чат-бота можно найти [по ссылке](https://hub.docker.com/repository/docker/vmstr8/discord-music-bot/general) (tags это и есть версии). Ну или просто вписывайте **latest**.

После создания файлов пропишите в консоле команду `docker-compose up -d`. Бот должен запуститься. Смотрите [Docker Compose Up](https://github.com/lavalink-devs/Lavalink#:~:text=d.%20See-,Docker%20Compose%20Up,-If%20your%20bot).