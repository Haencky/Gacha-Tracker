from dataclasses import dataclass

import requests
from django.core.files.base import ContentFile
from django.db.models import Q

from core.models import AbstractAttribute

from .models import Banner, DamageType, GachaTypes, Item, ItemTypes, Path, Warp

CELESTIAL_INVITES = [
    "1003",  # Himeko
    "1004",  # Welt
    "1101",  # Bronya
    "1102",  # Seele
    "1104",  # Gepard
    "1006",  # Silverwolf
    "1107",  # Clara
    "1205",  # Blade
    "1208",  # Fu Xuan
    "1209",  # Yanqing
    "1211",  # Bailu
    "1221",  # Yunli
    "1302",  # Argenti
    "23000",  # Night on the Milky Way
    "23002",  # Something Irreplaceable
    "23003",  # But the Battle Isn't Over
    "23004",  # In the Name of the World
    "23005",  # Moment of Victory
    "23012",  # Sleep Like the Dead
    "23013",  # Time Waits for No One
]

FRIBBELS_ELEMENTS = {
    "Lightning": "Thunder",
}  # mapping for element names to star rail res image names

IMAGE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
# icons for paths are icon/path/{Pathname}.png (capital)
# icons for elements are icon/element/{Element}.png (capital)
# icons for characters are icon/character/{Item_ID}.png
# images for characters are image/character_preview/{Item_ID}.png
# images for light cones are image/light_cone_portrait/{Item_ID}.png
# full arts for characters are image/character_portrait/{Item_ID}.png

ITEM_IMAGE_PATHS = {
    (ItemTypes.CHARACTER, "icon"): "icon/character/{item_id}.png",
    (ItemTypes.CHARACTER, "portrait"): "image/character_preview/{item_id}.png",
    (ItemTypes.CHARACTER, "fullart"): "image/character_portrait/{item_id}.png",
    (ItemTypes.LIGHT_CONE, "portrait"): "image/light_cone_portrait/{item_id}.png",
}

ATTRIBUTE_IMAGE_PATHS = {Path: "icon/path/{name}.png", DamageType: "icon/element/{name}.png"}


@dataclass
class ServiceCount:
    """
    Result class for counting service fails and successes

    Attributes:
        success(int): amount of successful
        fail(int): amount of failed
    """

    success: int
    fail: int


@dataclass
class ImageDownloadResult:
    """
    Support class to represent the result of updating images

    Attributes:
        item_icons(ServiceCount): information about item icons download
        item_portraits(ServiceCount): information about item portraits download
        path(ServiceCount): information about Path icon download
        dtype(ServiceCount): information about DamageType icon download
    """

    item_icons: ServiceCount
    item_portraits: ServiceCount
    path: ServiceCount
    dtype: ServiceCount


def attribute_image_url(obj: AbstractAttribute):
    """
    Build attribute image url

    Args:
       obj(AbstractAttribute): either Path or DamageType
    """
    name = obj.name if isinstance(obj, Path) else FRIBBELS_ELEMENTS.get(obj.name, obj.name)
    return IMAGE_URL + ATTRIBUTE_IMAGE_PATHS[type(obj)].format(name=name)


def item_image_url(item: Item, kind: str):
    """
    Builds image url

    Args:
        item(Item): item with missing images
        kind(str): kind of image (e.g. icon or portrait)
    """
    image_path = ITEM_IMAGE_PATHS[(item.item_type, kind)]
    return IMAGE_URL + image_path.format(item_id=item.item_id)


def _fetch_attribute_icon(attribute: type[AbstractAttribute]) -> ServiceCount:
    """
    Fetches missing icons for attribute types

    Args:
        attribute(AbstractAttribute): model to be updated

    Returns:
        result(tuple[int, int]): success count, fail count
    """
    entries = attribute.objects.filter(Q(icon__isnull=True) | Q(icon=""))
    failed = 0
    for e in entries:
        icon_url = attribute_image_url(e)
        try:
            response = requests.get(icon_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            failed += 1
            continue
        e.icon.save(name=f"{e.name}.png", content=ContentFile(response.content), save=True)
    return ServiceCount(success=(len(entries) - failed), fail=failed)


def _fetch_item_images(kind: str) -> ServiceCount:
    """
    Fetches missing images for items

    Args:
        kind(str): kind name (portrait or icon)

    Returns:
        result(tuple[int, int]): successfull downloads, failed downloads
    """
    item_types = [t for t, k in ITEM_IMAGE_PATHS if k == kind]
    items = Item.objects.filter(
        Q(**{f"{kind}__isnull": True}) | Q(**{kind: ""}), item_type__in=item_types
    )
    failed = 0

    for i in items:
        url = item_image_url(i, kind)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            failed += 1
            continue
        getattr(i, kind).save(
            name=f"{i.item_id}.png", content=ContentFile(response.content), save=True
        )
    return ServiceCount(success=len(items) - failed, fail=failed)


def download_missing_images() -> ImageDownloadResult:
    """
    Downloads all missing image files

    Returns:
        result(ImageDownloadResult): custom object containing count for success and fails
    """
    return ImageDownloadResult(
        item_icons=_fetch_item_images("icon"),
        item_portraits=_fetch_item_images("portrait"),
        path=_fetch_attribute_icon(Path),
        dtype=_fetch_attribute_icon(DamageType),
    )


def assign_featured_items() -> ServiceCount:
    """
    Tries to assign the featured time limited 5 star item to all banners

    Returns:
        result(ServiceCount): counts of successes and failures
    """
    missing = Banner.objects.filter(
        featured_item__isnull=True,
        gacha_type__in=[
            GachaTypes.LIGHT_CONE_EVENT,
            GachaTypes.CHARACTER_EVENT,
            GachaTypes.LIGHT_CONE_COLLABORATION,
            GachaTypes.CHARACTER_COLLABORATION,
        ],
    )
    failed = 0
    for b in missing:
        warps = b.warps
        featured: Warp = (
            warps.filter(item__rarity=5).exclude(item__item_id__in=CELESTIAL_INVITES).first()
        )
        if featured:
            b.featured_item = featured.item
            b.save()
        else:
            failed += 1
    return ServiceCount(success=missing.count() - failed, fail=failed)
