from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from django.db import transaction
from django.utils.text import slugify

from core.importer import AbstractParser, AbstractPullRecord, AbstractPullWriter, ImportResult

from .exceptions import (
    ApiConnectionError,
    AuthkeyError,
    AuthkeyTimeoutError,
    GachaTypeError,
    ItemCatalogError,
    ItemCatalogItemDoesNotExistError,
    ItemCatalogUnknownTypeError,
)
from .models import Banner, GachaTypes, Item, ItemTypes, Warp

FRIBBELS_ITEM_URL = "https://raw.githubusercontent.com/fribbels/hsr-optimizer/refs/heads/main/src/data/game_data.json"
FRIBBELS_ELEMENTS = {
    "Physical": "Physical",
    "Quantum": "Quantum",
    "Wind": "Wind",
    "Imaginary": "Imaginary",
    "Fire": "Fire",
    "Ice": "Ice",
    "Lightning": "Thunder",
}  # mapping for element names to star rail res image names
PRYDWEN_GUIDE = "https://www.prydwen.gg/star-rail/characters/{slug}"
PRYDWEN_SPECIAL_NAMES = {
    "1213": "imbibitor-lunae",
    "1413": "march-7th-evernight",
    "1224": "march-7th-swordmaster",
    "1507": "blade-mortenax",  # idk
    "1506": "silver-wolf-lv-999",  # django slugify error
    "1225": "tingyun-fugue",
    "1112": "topaz",  # where is numby ? :(
    "8001": "trailblazer-destoruction",
    "8002": "trailblazer-destruction",
    "8003": "trailblazer-preservation",
    "8004": "trailblazer-preservation",
    "8005": "trailblazer-harmony",
    "8006": "trailblazer-harmony",
    "8007": "trailblazer-remembrance",
    "8008": "trailblazer-remembrance",
    "8009": "trailblazer-elation",
    "8010": "trailblazer-elation",
}
IMAGE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
# icons for paths are icon/path/{Pathname}.png (capital)
# icons for elements are icon/element/{Element}.png (capital)
# icons for characters are icon/character/{Item_ID}.png
# images for characters are image/character_preview/{Item_ID}.png
# images for light cones are image/light_cone_portrait/{Item_ID}.png
# full arts for characters are image/character_portrait/{Item_ID}.png
API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global&size=5000"

PET_API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getBlindBoxLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global"
# authkey = {authkey}
# lang = {lang}

COLLAB_API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getLdGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global&size=5000"
# authkey={authkey}
# lang={lang}
# gacha_type={gacha_type}
GACHA_TYPE_URLS = {
    GachaTypes.STELLAR: API_URL,
    GachaTypes.DEPARTURE: API_URL,
    GachaTypes.CHARACTER_EVENT: API_URL,
    GachaTypes.LIGHT_CONE_EVENT: API_URL,
    GachaTypes.CHARACTER_COLLABORATION: COLLAB_API_URL,
    GachaTypes.LIGHT_CONE_COLLABORATION: COLLAB_API_URL,
}


# SUPPORT CLASSES #


class CatalogEntry:
    """
    Entry class for item catalog entries

    Attributes:
        eng_name(str): english item name
        item_id(str): item id
        damage_type(str): element of character
        path(str): name of path
        guide(str):
    """

    def __init__(
        self,
        eng_name: str,
        item_id: str,
        path: str,
        item_type: str,
        damage_type: str | None = None,
        guide: str = "",
    ):
        self.eng_name = eng_name
        self.item_id = item_id
        self.damage_type = damage_type
        self.path = path
        self.item_type = item_type
        self.guide = guide


class ItemCatalog:
    """
    Support class for holding all available items
    """

    def __init__(self, characters: dict, light_cones: dict):
        """
        Args:
            characters(dict): dictionary of fribbels characters
            light_cones(dict): dictionary of fribbels light cones
        """
        self.characters = characters
        self.light_cones = light_cones

    @classmethod
    def load(cls):
        try:
            response = requests.get(FRIBBELS_ITEM_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise ItemCatalogError("Could not get fribbels items") from e

        try:
            light_cones = data["lightCones"]
        except KeyError as e:
            raise ItemCatalogUnknownTypeError("lightcone is not a valid key in items") from e

        try:
            chars = data["characters"]
            characters = {key: value for key, value in chars.items() if key.isdigit()}
        except KeyError as e:
            raise ItemCatalogUnknownTypeError("characters is not a valid key in items") from e

        return cls(light_cones=light_cones, characters=characters)

    def get(self, item_id: str) -> CatalogEntry:
        """
        Returns a catalog entry object for specified id

        Args:
            item_id(str): item id to be returned

        Raises:
            ItemCatalogItemDoesNotExistError
        """
        if raw := self.characters.get(item_id):
            return CatalogEntry(
                item_id=raw["id"],
                eng_name=raw["name"],
                path=raw["path"],
                damage_type=raw["element"],
                item_type=ItemTypes.CHARACTER,
                guide=PRYDWEN_GUIDE.format(
                    slug=PRYDWEN_SPECIAL_NAMES.get(item_id, slugify(raw["name"]))
                ),
            )
        elif raw := self.light_cones.get(item_id):
            return CatalogEntry(
                item_id=raw["id"],
                eng_name=raw["name"],
                path=raw["path"],
                item_type=ItemTypes.LIGHT_CONE,
            )
        else:
            raise ItemCatalogItemDoesNotExistError(
                f"Item with item_id {item_id} does not exist in source"
            )


class WarpRecord(AbstractPullRecord):
    """
    Custom object for warp records

    Attributes:
        id(str): unique pull identifier
        uid(str): unique player identifer
        rarity(int): item rarity
        item_id(str): unique item identifier
        item_type(ItemType): either LC or character based on item_id
        item_name(str): item name
        gacha_type(str): gacha type (e.g 1 for "Stellar Warp")
        gacha_id(str): unique identifer for banner
        time(str): timestamp
        time_zone_offset(int): offset from UTC
    """

    def __init__(
        self,
        id: str,
        uid: str,
        rarity: str,
        item_id: str,
        item_name: str,
        gacha_type: str,
        gacha_id: str,
        time: str,
        time_zone_offset: int,
    ):
        self.id = id
        self.uid = uid
        self.rarity = rarity
        self.item_id = item_id
        self.item_type = ItemTypes.CHARACTER if int(self.item_id) < 20_000 else ItemTypes.LIGHT_CONE
        self.item_name = item_name
        self.gacha_type = gacha_type
        self.gacha_id = gacha_id
        self.time = time
        self.time_zone_offset = time_zone_offset

    def __eq__(self, other: WarpRecord):
        if not isinstance(other, WarpRecord):
            return False
        return self.id == other.id

    def __repr__(self):
        return f"{self.id} - {self.time} - {self.item_id}"

    def __hash__(self):
        return int(self.id)

    @property
    def aware_time(self):
        t = datetime.strptime(self.time, "%Y-%m-%d %H:%M:%S")
        tz = timezone(timedelta(hours=self.time_zone_offset))
        return t.replace(tzinfo=tz)


# PARSER #
class ApiParser(AbstractParser):
    def __init__(self, authkey: str, lang: str):
        self.authkey = authkey
        self.lang = lang

    def fetch(self) -> list[WarpRecord]:
        """
        Iterates over all gacha types and append gacha records

        Returns:
            records(list): a list of all gacha records (unsorted)

        Raises:
            ApiConnectionError
            AuthkeyError
            AuthkeyTimeoutError
            GachaTypeError
        """
        records = []
        for x in GACHA_TYPE_URLS:
            records.extend(self.fetch_gacha_type(x))
        return records

    def fetch_gacha_type(self, gacha_type: str) -> list[WarpRecord]:
        """
        Fetches all entries for given gacha_type from HoYos API

        Args:
            gacha_type(str): gacha type to be fetched

        Returns:
            records(list[WarpRecord]): list of all warp records

        Raises:
            ApiConnectionError
            AuthkeyTimeoutError
            AuthkeyError
            GachaTypeError
        """
        url = GACHA_TYPE_URLS.get(gacha_type)
        if url is None:
            raise GachaTypeError(f"Unknown gacha type: {gacha_type}")
        else:
            parsed = urlparse(url)

        query_dict = parse_qs(parsed.query)

        query_dict["gacha_type"] = [gacha_type]
        query_dict["authkey"] = [self.authkey]
        query_dict["lang"] = [self.lang]
        new_query = urlencode(query_dict, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))

        try:
            response = requests.get(url, timeout=10)
            if not response.status_code == 200:  # http code not "OK"
                raise ApiConnectionError("Invalid HTTP response")
            j = response.json()
            retcode = j["retcode"]
            if retcode == -101:  # http ok, authkey too old
                raise AuthkeyTimeoutError(j["message"], retcode=retcode)
            elif retcode == -100:  # invalid authkey
                raise AuthkeyError(j["message"], retcode=retcode)
            elif retcode != 0:
                raise ApiConnectionError(j["message"], retcode=retcode)  # other error
        except requests.RequestException as e:  # no http response
            raise ApiConnectionError("No HTTP response") from e

        data = j["data"]
        time_offset = data["region_time_zone"]
        entries = data["list"]

        return [
            WarpRecord(
                id=e["id"],
                uid=e["uid"],
                rarity=int(e["rank_type"]),
                item_id=e["item_id"],
                item_name=e["name"],
                gacha_type=gacha_type,
                gacha_id=e["gacha_id"],
                time=e["time"],
                time_zone_offset=time_offset,
            )
            for e in entries
        ]


# WRITER #
class RecordWriter(AbstractPullWriter):
    def __init__(self, item_catalog: ItemCatalog):
        """
        Args:
            item_catalog(ItemCatalog): item catalog providing all existing items
        """
        self.items = Item.objects.in_bulk()
        self.banners = Banner.objects.in_bulk()
        self.catalog = item_catalog

    def write(self, records: list[WarpRecord]) -> ImportResult:
        """
        Writes given record to DB

        Arguments:
           records(list): a list of warp records written to the db

        Returns:
            result(ImportResult): custom class
        """
        incoming_ids = [x.id for x in records]
        existing_ids = set(Warp.objects.filter(id__in=incoming_ids).values_list("id", flat=True))
        new_records = [r for r in records if r.id not in existing_ids]

        warps = []
        unknown_items = set()
        c_old_items = len(self.items)

        with transaction.atomic():
            for record in new_records:
                try:
                    item = self._get_item(record)
                except ItemCatalogItemDoesNotExistError:
                    unknown_items.add(record.item_id)
                    continue
                banner = self._get_banner(record.gacha_id)
                warps.append(
                    Warp(
                        item=item,
                        banner=banner,
                        gacha_type=record.gacha_type,
                        id=record.id,
                        uid=record.uid,
                        time=record.aware_time,
                    )
                )
            Warp.objects.bulk_create(warps)
        return ImportResult(
            created=len(warps),
            skipped=len(existing_ids),
            new_items=len(self.items) - c_old_items,
            unknown_items=unknown_items,
        )

    def _get_item(self, warp_record: WarpRecord) -> Item:
        """
        Returns an item from db or creates it

        Args:
            warp_record(WarpRecord): warprecord containing item information
        """
        item = self.items.get(warp_record.item_id)
        if item is not None:
            return item
        else:
            entry = self.catalog.get(warp_record.item_id)
            new_item = Item.objects.create_from_catalog(
                entry=entry, name=warp_record.item_name, rarity=warp_record.rarity
            )
            self.items[new_item.item_id] = new_item
            return new_item

    def _get_banner(self, gacha_id: str):
        banner = self.banners.get(gacha_id)
        if banner is not None:
            return banner
        else:
            banner = Banner.objects.create(gacha_id=gacha_id)
            self.banners[gacha_id] = banner
            return banner
