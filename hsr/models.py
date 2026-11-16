from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractAttribute, AbstractItem, AbstractPull

from .choices import ChromaAppearance, FiftyFifty, GachaTypes, ItemTypes
from .constants import CELESTIAL_INVITES

# Create your models here.


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


class ItemManager(models.Manager):
    """
    Custom manager to add functionalities for import
    """

    def create_from_catalog(self, entry, name):
        """
        Takes an catalog entry and creates specified item and all needed objects
        """
        path, _ = Path.objects.get_or_create(name=entry.path)
        if entry.damage_type:
            damage_type, _ = DamageType.objects.get_or_create(name=entry.damage_type)
        else:
            damage_type = None
        return self.create(
            name=name,
            rarity=entry.rarity,
            eng_name=entry.eng_name,
            path=path,
            damage_type=damage_type,
            item_type=entry.item_type,
            item_id=entry.item_id,
            guide=entry.guide,
        )


class Item(AbstractItem):
    """
    Item for HSR
    Inherits attributes from Abstract Item

    Attributes:
        path(Path): connection to path
        damage_type(DamageType | None): connection to damage type if exists
        item_type(str): either 'LIGHT CONE' or 'CHARACTER'
    """

    objects = ItemManager()
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

    @property
    def is_standard(self) -> bool:
        return self.item_id in CELESTIAL_INVITES

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
    gacha_type = models.CharField(
        max_length=30,
        verbose_name=_("Gacha Type"),
        help_text=_("Banner type the banner belongs to"),
        choices=GachaTypes,
    )

    class Meta:
        verbose_name = _("Banner")
        verbose_name_plural = _("Banners")

    def __str__(self):
        return (
            f"{self.featured_item.name} ({self.gacha_id})" if self.featured_item else self.gacha_id
        )


class Warp(AbstractPull):
    """
    Pull for HSR
    Inherits attributes from Abstract Pull
    """

    banner = models.ForeignKey(
        Banner,
        models.PROTECT,
        verbose_name=_("Banner"),
        help_text=_("Banner pull was made"),
        related_name="warps",
    )
    gacha_type = models.CharField(
        max_length=50,
        verbose_name=_("Gacha Type"),
        help_text=_("Identifier of the gacha pool (e.g. 1 for Stellar Warp)"),
        choices=GachaTypes,
    )

    pity = models.IntegerField(
        verbose_name=_("Pity"), help_text=_("pull pity (1-xx)"), null=True, blank=True
    )

    fifty_fifty = models.CharField(
        blank=True,
        choices=FiftyFifty,
        default=FiftyFifty.NONE,
        max_length=10,
        verbose_name=_("Fifty Fifty"),
        help_text=_("Info about fifty fifty won or loss"),
    )

    featured_pity = models.IntegerField(
        verbose_name=_("Featured pity"),
        help_text=_("Pity required for featured item"),
        null=True,
        blank=True,
    )

    @property
    def is_lost(self):
        return self.fifty_fifty == FiftyFifty.LOST

    @property
    def is_highest_rank(self):
        return self.item.rarity == 5

    class Meta(AbstractPull.Meta):
        verbose_name = _("Warp")
        verbose_name_plural = _("Warps")
        ordering = ["id"]
        indexes = [models.Index(fields=["gacha_type", "id"])]


class PetType(models.Model):
    """
    Pet Types (banner?)
    """

    type_id = models.CharField(
        max_length=5, verbose_name=_("Type ID"), help_text=_("Type identifier"), primary_key=True
    )
    type_name = models.CharField(
        max_length=50, verbose_name=_("Type Name"), help_text=_("Type Name")
    )

    class Meta:
        verbose_name = _("Pet Type")
        verbose_name_plural = _("Pet Types")
        ordering = ["type_id"]

    def __str__(self):
        return f"{self.type_name} ({self.type_id})"


class PetPool(models.Model):
    pool_id = models.CharField(max_length=6, verbose_name=_("Pool ID"), primary_key=True)

    class Meta:
        verbose_name = _("Pet Pool")
        verbose_name_plural = _("Pet Pools")
        ordering = ["pool_id"]

    def __str__(self):
        return f"{self.pool_id}"


class Pet(models.Model):
    """
    Pet (special item)
    """

    name = models.CharField(
        verbose_name=_("Name"), max_length=50, help_text=_("Pet Name (default)"), blank=True
    )
    pet_id = models.CharField(
        verbose_name=_("Pet ID"),
        max_length=10,
        help_text=_("Unique Pet identifier"),
        primary_key=True,
    )
    item_id = models.CharField(  # seems to be identical with pet id
        verbose_name=_("Unique item identifier"),
        max_length=10,
        help_text=_("Unique item identifier"),
    )

    pet_type = models.ForeignKey(
        PetType, on_delete=models.PROTECT, related_name="pets", verbose_name=_("Pet Type")
    )

    class Meta:
        verbose_name = _("Pet")
        verbose_name_plural = _("Pets")

    def __str__(self):
        return f"{self.name} ({self.pet_id})"


class PetVariant(models.Model):
    """
    Defines variants (shiny, normal, etc.)
    """

    pet = models.ForeignKey(
        Pet,
        on_delete=models.PROTECT,
        verbose_name=_("Pet"),
        help_text=_("Reference to pet"),
        related_name="variants",
    )
    name = models.CharField(verbose_name="Variant name", help_text=_("Variant name"), max_length=50)
    chroma_appearance_id = models.CharField(
        verbose_name=_("Chroma ID"),
        help_text=_("Defines if normal or collector"),
        choices=ChromaAppearance,
        default=ChromaAppearance.NORMAL,
        max_length=2,
    )
    blind_box_sub_rarity = models.CharField(
        verbose_name=_("Sub Rarity"),
        help_text=_("Sub rarity in blind box"),
        max_length=3,  # most likely fixed options
    )
    portrait = models.ImageField(
        verbose_name=_("Portrait"), null=True, blank=True, upload_to="hsr/pet/portrait"
    )

    icon = models.ImageField(
        verbose_name=_("Icon"), null=True, blank=True, upload_to="hsr/pet/icon"
    )

    class Meta:
        verbose_name = _("Pet Variant")
        verbose_name_plural = _("Pet Variants")
        constraints = [
            models.UniqueConstraint(
                fields=["pet", "chroma_appearance_id"], name="unique_pet_variant"
            )
        ]

    def __str__(self):
        return self.name


class PetPull(models.Model):
    """
    Pull entry for pets
    """

    id = models.CharField(
        max_length=20, verbose_name=_("ID"), help_text=_("Pet Pull ID"), primary_key=True
    )
    time = models.DateTimeField(verbose_name=_("Time"), null=True, blank=True)
    pool = models.ForeignKey(PetPool, on_delete=models.PROTECT, verbose_name=_("Pool"))
    pet_variant = models.ForeignKey(
        PetVariant, on_delete=models.PROTECT, verbose_name=_("Pet Variant"), related_name="pulls"
    )
    uid = models.CharField(max_length=20, verbose_name=_("UID"), help_text=_("Account identifier"))

    class Meta:
        verbose_name = _("Pet Pull")
        verbose_name_plural = _("Pet Pulls")
        ordering = ["id"]

    def __str__(self):
        return self.pet_variant.name
