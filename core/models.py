from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.


def item_image_path(instance, filename):
    return f"items/{instance._meta.app_label}/{filename}"


class AbstractPull(models.Model):
    id = models.CharField(max_length=100, verbose_name=_("Pull id"), primary_key=True)
    uid = models.CharField(
        max_length=50, verbose_name=_("UID"), help_text=_("User connected to this pull")
    )
    gacha_type = models.CharField(
        max_length=8,
        verbose_name=_("Gacha Type"),
        help_text=_("Identifier of the gacha pool, defined by the game"),
    )
    time = models.DateTimeField(verbose_name=_("Time"), help_text=_("Timestamp pull was made"))

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.id} - {self.uid}"


class AbstractItem(models.Model):
    item_id = models.CharField(max_length=50, verbose_name=_("Item ID"), help_text=_("Unique ID"))
    name = models.CharField(max_length=100, verbose_name=_("Name"), help_text=_("Name of item"))
    rarity = models.IntegerField(verbose_name=_("Rarity"), help_text=_("Rarity of item"))
    image = models.ImageField(
        null=True,
        blank=True,
        upload_to=item_image_path,
        verbose_name=_("Image"),
        help_text=_("Image to be displayed"),
    )
    guide = models.URLField(blank=True, verbose_name=_("Guide"), help_text=_("Link to build guide"))

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name} ({self.item_id})"
