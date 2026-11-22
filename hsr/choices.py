from django.db import models
from django.utils.translation import gettext_lazy as _


class ItemTypes(models.TextChoices):
    """
    Item Types
    Either CHARACTER or LIGHT CONE
    """

    CHARACTER = "CHARACTER", _("Character")
    LIGHT_CONE = "LIGHT CONE", _("Light Cone")


class GachaTypes(models.TextChoices):
    STELLAR = "1", _("Stellar Warp")
    DEPARTURE = "2", _("Departure Warp")
    CHARACTER_EVENT = "11", _("Character Event Warp")
    LIGHT_CONE_EVENT = "12", _("Light Cone Event Warp")
    CHARACTER_COLLABORATION = "21", _("Character Collaboration Warp")
    LIGHT_CONE_COLLABORATION = "22", _("Light Cone Collaboration Warp")


class ChromaAppearance(models.TextChoices):
    NORMAL = "0", _("Normal")
    COLLECTOR = "1", _("Collector")
