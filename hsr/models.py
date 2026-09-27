from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractAttribute, AbstractItem, AbstractPull

# Create your models here.


class ItemTypes(models.TextChoices):
    """
    Item Types
    Either CHARACTER or LIGHT CONE
    """

    CHARACTER = "CHARACTER", _("Character")
    LIGHT_CONE = "LIGHT CONE", _("Light Cone")


class GachaTypes(models.TextChoices):
    STELLAR = "1", _("Stellar Warp")
    DEPARTURE = "2", _("Depature Warp")
    CHARACTER_EVENT = "11", _("Character Event Warp")
    LIGHT_CONE_EVENT = "12", _("Light Cone Event Warp")
    CHARACTER_COLLABORATION = "21", _("Character Collaboration Warp")
    LIGHT_CONE_COLLABORATION = "22", _("Light Cone Collaboration Warp")


class Path(AbstractAttribute):
    """
    Path of lightcones and characters (e.g. nihility)
    Inherits attributes from Abstract Attributes
    """

    class Meta(AbstractAttribute.Meta):
        verbose_name = _("Path")
        verbose_name_plural = _("Paths")


class DamageType(AbstractAttribute):
    """
    Damage Type (e.g. wind)
    Inherits attributes from Abstract Attribute
    """

    class Meta(AbstractAttribute.Meta):
        verbose_name = _("Damage Type")
        verbose_name_plural = _("Damage Types")


class Item(AbstractItem):
    """
    Item for HSR
    Inherits attributes from Abstract Item

    Attributes:
        path(Path): connection to path
        damage_type(DamageType | None): connection to damage type if exists
        item_type(str): either 'LIGHT CONE' or 'CHARACTER'
    """

    path = models.ForeignKey(
        Path,
        on_delete=models.PROTECT,
        verbose_name=_("Path"),
        help_text=_("Path of item (e.g. 'Nihility' for 'Acheron')"),
        related_name="items",
    )

    damage_type = models.ForeignKey(
        DamageType,
        on_delete=models.PROTECT,
        verbose_name=_("Damage Type"),
        help_text=_("Damage Type of character (e.g. wind)"),
        related_name="characters",
        null=True,  # light cones dont have one
        blank=True,  # light cones dont have one
    )

    item_type = models.CharField(
        max_length=50,
        choices=ItemTypes,
        default=ItemTypes.LIGHT_CONE,
        verbose_name=_("Item Type"),
        help_text=_("Character or Light Cone"),
    )

    class Meta(AbstractItem.Meta):
        verbose_name = _("Item")
        verbose_name_plural = _("Items")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(item_type=ItemTypes.CHARACTER, damage_type__isnull=False)
                    | models.Q(item_type=ItemTypes.LIGHT_CONE, damage_type__isnull=True)
                ),
                name="hsr_item_damage_type_matches_item_type",
            )
        ]


class Banner(models.Model):
    """
    Banner representing a specific run of limited item

    Attributes:
        name(str): banner name
        featured_item(Item): featured item
        gacha_id(str): banner ID provided by HoYos API
    """

    name = models.CharField(
        max_length=50, verbose_name=_("Name"), help_text=_("Banner name"), blank=True
    )
    featured_item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        verbose_name=_("Item"),
        help_text=_("Featured item obtain(able) on the banner"),
        blank=True,
        null=True,
        related_name="featured_banners",
    )
    gacha_id = models.CharField(
        max_length=20,
        verbose_name=_("Gacha ID"),
        help_text=_("Gacha ID provided by HoYos API"),
        primary_key=True,
    )

    class Meta:
        verbose_name = _("Banner")
        verbose_name_plural = _("Banners")

    def __str__(self):
        return f"{self.gacha_id}" if self.featured_item + f" - {self.featured_item.name}" else ""


class Warp(AbstractPull):
    """
    Pull for HSR
    Inherits attributes from Abstract Pull
    """

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        help_text=_("Item obtained in warp"),
        verbose_name=_("Item"),
        related_name="warps",
    )

    banner = models.ForeignKey(
        Banner, models.PROTECT, verbose_name=_("Banner"), help_text=_("Banner pull was made")
    )
    gacha_type = models.CharField(
        max_length=50,
        verbose_name=_("Gacha Type"),
        help_text=_("Identifier of the gacha pool (e.g. 1 for Stellar Warp)"),
        choices=GachaTypes,
    )

    class Meta(AbstractPull.Meta):
        verbose_name = _("Warp")
        verbose_name_plural = _("Warps")
