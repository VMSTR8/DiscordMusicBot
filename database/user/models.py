from tortoise.models import Model
from tortoise import fields


class User(Model):
    """
    Model class representing a Discord user.

    Attributes:
        id (int): Primary key for the User.
        discord_id (int): Unique identifier for the Discord user.
        waifu_links (ReverseRelation): Reverse relation
        to associated UserWaifuLink instances.

    Methods:
        __str__(): Returns a string representation of the user.
    """
    id = fields.IntField(pk=True)
    discord_id = fields.IntField(unique=True)

    waifu_links = fields.ReverseRelation["UserWaifuLink"]

    def __str__(self):
        return self.discord_id


class Waifu(Model):
    """
    Model class representing a waifu character.

    Attributes:
        id (int): Primary key for the Waifu.
        shikimori_id (int): Identifier for the waifu on Shikimori.
        waifu_name (str): Name of the waifu.
        waifu_name_rus (str): Russian name of the waifu.
        image (str): URL of the waifu's image.
        url (str): URL link to the waifu's page.
        alt_name (str): Alternate names of the waifu.
        japanese_name (str): Japanese name of the waifu.
        user_links (ReverseRelation): Reverse relation
        to associated UserWaifuLink instances.

    Methods:
        __str__(): Returns a string representation of the waifu.
    """
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
    """
    Model class representing a link between a user and a waifu.

    Attributes:
        id (int): Primary key for the UserWaifuLink.
        user (ForeignKeyField): Foreign key to associated User instance.
        waifu (ForeignKeyField): Foreign key to associated Waifu instance.
        true_love (bool): Indicates if it's a "true love"
        link between user and waifu.

    Meta:
        unique_together: Ensures that each user
        can have only one link to each waifu.

    Methods:
        __str__(): Returns a string representation of the link.
    """
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="waifu_links")
    waifu = fields.ForeignKeyField("models.Waifu", related_name="user_links")
    true_love = fields.BooleanField(default=False)

    class Meta:
        unique_together = (("user", "waifu"),)

    def __str__(self):
        return f"{self.user.discord_id} - {self.waifu.waifu_name}"
