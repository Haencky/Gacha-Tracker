from dataclasses import dataclass

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q

from core.models import AbstractAttribute

from .choices import FiftyFifty, GachaTypes, ItemTypes
from .constants import CELESTIAL_INVITES, FEATURED_TYPES
from .models import Banner, DamageType, Item, Path, Warp

IMAGE_URL = (
    "https://raw.githubusercontent.com/fribbels/hsr-optimizer/refs/heads/main/public/assets/"
)
# icons for paths are icon/path/{Pathname}.webp (capital)
# icons for elements are icon/element/{Element}.webp (capital)
# icons for characters are icon/avatar/{Item_ID}.webp
# images for characters are image/character_preview/{Item_ID}.webp
# images for light cones are image/light_cone_portrait/{Item_ID}.webp
# full arts for characters are image/character_portrait/{Item_ID}.webp

ITEM_IMAGE_PATHS = {
    (ItemTypes.CHARACTER, "icon"): "icon/avatar/{item_id}.webp",
    (ItemTypes.CHARACTER, "portrait"): "image/character_preview/{item_id}.webp",
    (ItemTypes.CHARACTER, "fullart"): "image/character_portrait/{item_id}.webp",
    (ItemTypes.LIGHT_CONE, "portrait"): "image/light_cone_portrait/{item_id}.webp",
    (ItemTypes.LIGHT_CONE, "icon"): "icon/light_cone/{item_id}.webp",
}

ATTRIBUTE_IMAGE_PATHS = {Path: "icon/path/{name}.webp", DamageType: "icon/element/{name}.webp"}


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
    return IMAGE_URL + ATTRIBUTE_IMAGE_PATHS[type(obj)].format(name=obj.name)


def item_image_url(item_id: str, item_type: ItemTypes, kind: str):
    """
    Builds image url

    Args:
        item(Item): item with missing images
        kind(str): kind of image (e.g. icon or portrait)
    """
    image_path = ITEM_IMAGE_PATHS[(item_type, kind)]
    return IMAGE_URL + image_path.format(item_id=item_id)


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


def _fetch_item_images(catalog, kind: str) -> ServiceCount:
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
        url = item_image_url(item_id=catalog.image_id(i.item_id), item_type=i.item_type, kind=kind)
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


def download_missing_images(catalog) -> ImageDownloadResult:
    """
    Downloads all missing image files

    Returns:
        result(ImageDownloadResult): custom object containing count for success and fails
    """
    return ImageDownloadResult(
        item_icons=_fetch_item_images(catalog, "icon"),
        item_portraits=_fetch_item_images(catalog, "portrait"),
        path=_fetch_attribute_icon(Path),
        dtype=_fetch_attribute_icon(DamageType),
    )


def assign_featured_items() -> ServiceCount:
    """
    Tries to assign the featured time limited 5 star item to all banners

    Returns:
        result(ServiceCount): counts of successes and failures
    """
    missing = Banner.objects.filter(featured_item__isnull=True, gacha_type__in=FEATURED_TYPES)
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
    return ServiceCount(success=len(missing) - failed, fail=failed)


def recalculate_pity() -> None:
    """
    Recalculates pity and assignes 50/50 wins
    """
    updated = []
    for g in GachaTypes:
        pity = 0
        featured_pity = 0
        guaranteed = False
        warps = Warp.objects.select_related("item", "banner__featured_item").filter(gacha_type=g)
        has_50_50 = g in FEATURED_TYPES
        for w in warps:
            pity += 1
            featured_pity += 1
            w.pity = pity
            w.fifty_fifty = ""
            w.featured_pity = None
            if w.is_highest_rank:
                if has_50_50:
                    if w.banner.featured_item is not None:
                        lost = w.item.item_id != w.banner.featured_item.item_id
                    else:
                        lost = w.item.item_id in CELESTIAL_INVITES
                    if not guaranteed:
                        if lost:
                            w.fifty_fifty = FiftyFifty.LOST
                        else:
                            w.fifty_fifty = FiftyFifty.WON
                            w.featured_pity = featured_pity
                            featured_pity = 0
                    else:
                        w.fifty_fifty = FiftyFifty.GUARANTEED
                        w.featured_pity = featured_pity
                        featured_pity = 0
                    guaranteed = lost
                else:
                    w.featured_pity = pity
                    featured_pity = 0
                pity = 0

            updated.append(w)

    with transaction.atomic():
        Warp.objects.bulk_update(updated, ["pity", "fifty_fifty", "featured_pity"], batch_size=500)
