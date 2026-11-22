from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractAttribute, AbstractItem, AbstractPityPull

from .choices import GachaTypes, ItemTypes
from .constants import STANDARD_ITEMS


# Create your models here.
class Element(AbstractAttribute):
    """
    Element of character
    """

    class Meta(AbstractAttribute.Meta):
        verbose_name = _("Element")
        verbose_name_plural = _("Elements")


class WeaponType(AbstractAttribute):
    """
    Weapon Type
    """

    class Meta(AbstractAttribute.Meta):
        verbose_name = _("Weapon Type")
        verbose_name_plural = _("Weapon Types")


class Item(AbstractItem):
    """
    General Item
    """

    element = models.ForeignKey(
        Element,
        null=True,
        blank=True,
        verbose_name=_("Element"),
        help_text=_("Element (only used for characters)"),
        related_name="items",
        on_delete=models.PROTECT,
    )

    weapon_type = models.ForeignKey(
        WeaponType,
        verbose_name=_("Weapon Type"),
        help_text=_("Weapon Type of item"),
        related_name="items",
        on_delete=models.PROTECT,
    )

    item_type = models.CharField(
        max_length=10, choices=ItemTypes, verbose_name=_("Item Type"), help_text=_("Type of item")
    )

    class Meta:
        verbose_name = _("Item")
        verbose_name_plural = _("Items")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(item_type=ItemTypes.WEAPON, element__isnull=True)
                    | models.Q(item_type=ItemTypes.CHARACTER, element__isnull=False)
                ),
                name="genshin_element_matches_item_type",
            )
        ]

    @property
    def is_standard(self):
        return self.item_id in STANDARD_ITEMS


class Wish(AbstractPityPull):
    """
    Genshin pull
    """

    gacha_type = models.CharField(max_length=30, verbose_name=_("Gacha Type"), choices=GachaTypes)
    item = models.ForeignKey(
        Item,
        verbose_name=_("Item"),
        help_text=_("Item obtained in this wish"),
        on_delete=models.PROTECT,
        related_name="wishes",
    )

    class Meta(AbstractPityPull.Meta):
        verbose_name = _("Wish")
        verbose_name_plural = _("Wishes")
        ordering = ["id"]
        indexes = [models.Index(fields=("gacha_type", "id"))]

    @property
    def is_highest_rank(self):
        return self.item.rarity == 5
