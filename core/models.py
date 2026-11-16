from pathlib import Path

from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


# Create your models here.
@deconstructible
class UploadTo:
    """
    Upload to callable that stores files grouped by game and model

    Args:
        field(str): name of the model field used as filename (e.g. 'name')
        subfolder(str): subfolder (e.g. 'portrait' or 'icon')
    """

    def __init__(self, field: str, subfolder: str = ""):
        self.field = field
        self.subfolder = subfolder

    def __call__(self, instance, filename):
        path = [instance._meta.app_label, instance._meta.model_name]
        if self.subfolder:
            path.append(self.subfolder)
        stem = slugify(str(getattr(instance, self.field)))
        suffix = Path(filename).suffix.lower()
        path.append(f"{stem}{suffix}")
        return "/".join(path)


class AbstractItem(models.Model):
    """
    Abstract base class for items

    Attributes:
        item_id(str): item identifier
        name(str): item name
        eng_name(str): english item name
        rarity(int): rarity
        portrait(str|None): reference to portrait image
        icon(str|None): reference to icon image
        guide(str): url to prydwen (or other guide) link
    """

    item_id = models.CharField(
        max_length=50, verbose_name=_("Item ID"), help_text=_("Unique ID"), primary_key=True
    )
    name = models.CharField(max_length=100, verbose_name=_("Name"), help_text=_("Name of item"))
    eng_name = models.CharField(
        max_length=100, verbose_name=_("English Name"), help_text=_("English Name of item")
    )
    rarity = models.IntegerField(verbose_name=_("Rarity"), help_text=_("Rarity of item"))
    portrait = models.ImageField(
        null=True,
        blank=True,
        upload_to=UploadTo("item_id", "portrait"),
        verbose_name=_("Item Portrait"),
        help_text=_("Image to be displayed"),
    )
    icon = models.ImageField(
        null=True,
        blank=True,
        upload_to=UploadTo("item_id", "icon"),
        verbose_name=_("Item Icon"),
        help_text=_("Small icon to be displayed"),
    )
    guide = models.URLField(blank=True, verbose_name=_("Guide"), help_text=_("Link to build guide"))

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name} ({self.item_id})"


class AbstractPull(models.Model):
    """
    Abstract base class for pulls

    Attributes:
        id(str): game specific pull id
        uid(str): user identifier
        gacha_type(str): banner pool (not banner)
        time(str): timestamp
    """

    id = models.CharField(max_length=100, verbose_name=_("Pull id"), primary_key=True)
    uid = models.CharField(
        max_length=50, verbose_name=_("UID"), help_text=_("User connected to this pull")
    )
    gacha_type = models.CharField(
        max_length=8,
        verbose_name=_("Gacha Type"),
        help_text=_("Identifier of the gacha pool, defined by the game"),
    )
    time = models.DateTimeField(
        verbose_name=_("Time"), help_text=_("Timestamp pull was made"), null=True, blank=True
    )

    item = models.ForeignKey(
        "Item",
        help_text=_("Item obtained in pull"),
        verbose_name=_("Item"),
        related_name="%(class)ss",
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.id} - {self.time}"

    @property
    def is_highest_rank(self):
        """
        Returns true if the pull contains the highest available rarity
        """
        raise NotImplementedError

    @property
    def is_lost(self):
        """
        Returns true if contains a standard item
        """
        raise NotImplementedError


class AbstractAttribute(models.Model):
    """
    Abstract base class for game specific attributes

    Attributes:
        name(str): unique attribute name
        icon(str): attribute icon
    """

    name = models.CharField(
        max_length=50,
        verbose_name=_("Name"),
        help_text=_("Name of attribute"),
        unique=True,
    )
    icon = models.ImageField(
        verbose_name=_("Attribute icon"),
        help_text=_("Attribute icon"),
        null=True,
        blank=True,
        upload_to=UploadTo("name"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name}"
