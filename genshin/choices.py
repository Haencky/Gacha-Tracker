from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class ItemTypes(TextChoices):
    """
    Item type
    Either weapon or character
    """

    WEAPON = "WEAPON", _("Weapon")
    CHARACTER = "CHARACTER", _("Character")


class GachaTypes(TextChoices):
    BEGINNER = "100", _("Beginners' Wish")
    STANDARD = "200", _("Standard Wish")
    CHARACTER_EVENT = "301", _("Character Event Wish")
    CHARACTER_EVENT_2 = "400", _("Character Event Wish-2")
    WEAPON_EVENT = "302", _("Weapon Event Wish")
    CHRONICLED = "500", _("Chronicled Wish")
