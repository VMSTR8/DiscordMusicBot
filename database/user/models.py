from tortoise.models import Model
from tortoise import fields


class User(Model):
    id = fields.IntField(pk=True)
    discord_id = fields.IntField(unique=True)
    # join_date = fields.DatetimeField(auto_now_add=True)

    waifu_links = fields.ReverseRelation["UserWaifuLink"]

    def __str__(self):
        return self.discord_id


class Waifu(Model):
    id = fields.IntField(pk=True)
    shikimori_id = fields.IntField()
    waifu_name = fields.CharField(max_length=255)
    waifu_name_rus = fields.CharField(max_length=255)
    image = fields.CharField(max_length=255)
    url = fields.CharField(max_length=255)
    alt_name = fields.TextField(max_length=1000)
    japanese_name = fields.CharField(max_length=255)

    user_links = fields.ReverseRelation["UserWaifuLink"]

    def __str__(self):
        return self.waifu_name


class UserWaifuLink(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="waifu_links")
    waifu = fields.ForeignKeyField("models.Waifu", related_name="user_links")
    true_love = fields.BooleanField(default=False)

    class Meta:
        unique_together = (("user", "waifu"),)

    def __str__(self):
        return f"{self.user.discord_id} - {self.waifu.waifu_name}"
