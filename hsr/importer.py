import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from django.db import transaction
from django.utils.text import slugify

from core.importer import AbstractParser, AbstractPullRecord, AbstractPullWriter, ImportResult

from .choices import ChromaAppearance
from .exceptions import (
    ApiConnectionError,
    AuthkeyError,
    AuthkeyTimeoutError,
    GachaTypeError,
    ItemCatalogError,
    ItemCatalogItemDoesNotExistError,
    ItemCatalogUnknownTypeError,
    LegacyFileError,
    RateLimitError,
    UIDError,
)
from .models import (
    Banner,
    GachaTypes,
    Item,
    ItemTypes,
    Pet,
    PetPool,
    PetPull,
    PetType,
    PetVariant,
    Warp,
)
from .services import item_image_url

PET_PAGE_SIZE = 5
FRIBBELS_ITEM_URL = "https://raw.githubusercontent.com/fribbels/hsr-optimizer/refs/heads/main/src/data/game_data.json"
PRYDWEN_GUIDE = "https://www.prydwen.gg/star-rail/characters/{slug}"
PRYDWEN_SPECIAL_NAMES = {
    "1213": "imbibitor-lunae",
    "1413": "march-7th-evernight",
    "1224": "march-7th-swordmaster",
    "1507": "blade-mortenax",  # idk
    "1506": "silver-wolf-lv-999",  # django slugify error
    "1225": "tingyun-fugue",
    "1112": "topaz",  # where is numby ? :(
    "1511": "aha",
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
API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global"

PET_API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getBlindBoxLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global"
# authkey = {authkey}
# lang = {lang}

COLLAB_API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getLdGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global"
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

# legacy warps reference banners by their autoincrement id, gacha_id comes from the join
LEGACY_QUERY = """
    SELECT w.warp_id, w.uid, w.time,
           b.gacha_id, g.gacha_type,
           i.item_id, i.name, i.rarity
    FROM warptracker_warp w
    JOIN warptracker_banner b ON b.id = w.gacha_id_id
    JOIN warptracker_gachatype g ON g.id = b.gacha_type_id
    JOIN warptracker_item i ON i.item_id = w.item_id_id
    ORDER BY w.warp_id
"""
STANDARD_BANNER_ID = "1001"
PULL_ID_LENGTH = 19
MAX_ATTEMPTS = 3
REQUEST_DELAY = 0.3


# SUPPORT FUNCTIONS
def build_api_url(gacha_type: str, authkey: str, lang: str, size: int):
    """
    Builds the url

    Args:
        gacha_type(str): gacha type
        authkey(str): authkey
        lang(str): language code
    """
    url = GACHA_TYPE_URLS.get(gacha_type)
    if url is None:
        raise GachaTypeError(f"Unknown gacha type: {gacha_type}")
    else:
        parsed = urlparse(url)

    query_dict = parse_qs(parsed.query)

    query_dict["gacha_type"] = [gacha_type]
    query_dict["authkey"] = [authkey]
    query_dict["lang"] = [lang]
    query_dict["size"] = [size]
    new_query = urlencode(query_dict, doseq=True)
    url = urlunparse(parsed._replace(query=new_query))

    return url


def _api_get(url: str) -> dict:
    """
    Support function for calling hoyos API

    Args:
        url(str): url endpoint

    Returns:
        data(dict): data returned from the api
    """
    time.sleep(REQUEST_DELAY)
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            j = response.json()
        except requests.RequestException as e:  # no http response
            raise ApiConnectionError("No HTTP response") from e
        retcode = j["retcode"]
        if retcode == 0:
            if j.get("data") is None:
                raise ApiConnectionError("API returned no data")
            return j["data"]
        elif retcode == -110:  # visited to often
            time.sleep(2**attempt)
            continue
        elif retcode == -101:  # http ok, authkey too old
            raise AuthkeyTimeoutError(j["message"], retcode=retcode)
        elif retcode == -100:  # invalid authkey
            raise AuthkeyError(j["message"], retcode=retcode)
        elif retcode != 0:
            raise ApiConnectionError(j["message"], retcode=retcode)  # other error

    raise RateLimitError("Visited too frequently", retcode=-110)


# SUPPORT CLASSES #


class CatalogEntry:
    """
    Entry class for item catalog entries

    Attributes:
        eng_name(str): english item name
        item_id(str): item id
        damage_type(str): element of character
        path(str): name of path
        guide(str): url to prydwen guide
        rarity(str): rarity
    """

    def __init__(
        self,
        eng_name: str,
        item_id: str,
        item_type: str,
        rarity: str,
        path: str | None = None,
        damage_type: str | None = None,
        guide: str = "",
    ):
        self.eng_name = eng_name
        self.item_id = item_id
        self.damage_type = damage_type
        self.rarity = rarity
        self.path = path
        self.item_type = item_type
        self.guide = guide


class ItemCatalog:
    """
    Support class for holding all available items
    """

    def __init__(self, characters: dict, light_cones: dict, image_ids: dict):
        """
        Args:
            characters(dict): dictionary of fribbels characters
            light_cones(dict): dictionary of fribbels light cones
            image_ids(dict): dictionary of items with nova flare
        """
        self.characters = characters
        self.light_cones = light_cones
        self.image_ids = image_ids

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
            image_ids = {key.removesuffix("b1"): key for key in chars if key.endswith("b1")}
            characters = {key: value for key, value in chars.items() if key.isdigit()}
        except KeyError as e:
            raise ItemCatalogUnknownTypeError("characters is not a valid key in items") from e

        return cls(light_cones=light_cones, characters=characters, image_ids=image_ids)

    def image_id(self, item_id: str) -> str:
        """
        Returns the correct image id
        """
        return self.image_ids.get(item_id, item_id)

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
                rarity=raw["rarity"],
            )
        elif raw := self.light_cones.get(item_id):
            return CatalogEntry(
                item_id=raw["id"],
                eng_name=raw["name"],
                path=raw["path"],
                item_type=ItemTypes.LIGHT_CONE,
                rarity=raw["rarity"],
            )
        else:
            raise ItemCatalogItemDoesNotExistError(
                f"Item with item_id {item_id} does not exist in source"
            )

    def all(self) -> list[CatalogEntry]:
        """
        Returns catalog entries for all existing items

        Returns:
            items(list): list of all items as CatalogEntry
        """
        ret = []
        ret.extend(
            [
                {
                    "name": c["name"],
                    "item_id": c["id"],
                    "item_type": ItemTypes.CHARACTER,
                    "rarity": c["rarity"],
                    "image_url": item_image_url(
                        self.image_ids.get(c["id"], c["id"]),
                        item_type=ItemTypes.CHARACTER,
                        kind="icon",
                    ),
                    "unreleased": c["unreleased"],
                }
                for _, c in self.characters.items()
            ]
        )
        ret.extend(
            [
                {
                    "name": lc["name"],
                    "item_id": lc["id"],
                    "item_type": ItemTypes.LIGHT_CONE,
                    "rarity": lc["rarity"],
                    "image_url": item_image_url(
                        lc["id"], item_type=ItemTypes.LIGHT_CONE, kind="icon"
                    ),
                    "unreleased": lc["unreleased"],
                }
                for _, lc in self.light_cones.items()
            ]
        )
        return ret


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
        if not self.time:  # legacy records may have no timestamp
            return None
        t = datetime.strptime(self.time, "%Y-%m-%d %H:%M:%S")
        tz = timezone(timedelta(hours=self.time_zone_offset))
        return t.replace(tzinfo=tz)


class PetRecord(AbstractPullRecord):
    """
    Custom object for pet entries

    Attributes:
        id(str): identifier for pet pull
        pool_id(str): pool identifier
        item_id(str): item id
        item_name(str): pet name
        pet_id(str): pet id (most likely identical to item_id)
        chroma_appearance_id(str): "shiny" value
        pet_type(str): series identifier (i guess), based on type name
        blind_box_sub_rarity(str): rarity (based on type and chroma experience)
        type_name(str): pet type name
        time(str): timestamp
        uid(str): account identifier
        time_zone_offset(int): offset to utc
    """

    def __init__(
        self,
        id: str,
        pool_id: str,
        item_id: str,
        item_name: str,
        pet_id: str,
        chroma_appearance_id: str,
        pet_type: str,
        blind_box_sub_rarity: str,
        type_name: str,
        time: str,
        uid: str,
        time_zone_offset: int,
    ):
        self.id = id
        self.pool_id = pool_id
        self.item_id = item_id
        self.item_name = item_name
        self.pet_id = pet_id
        self.chroma_appearance_id = chroma_appearance_id
        self.pet_type = pet_type
        self.blind_box_sub_rarity = blind_box_sub_rarity
        self.type_name = type_name
        self.time = time
        self.uid = uid
        self.time_zone_offset = time_zone_offset

    def __eq__(self, other):
        if not isinstance(other, PetRecord):
            return False
        return self.id == other.id

    def __repr__(self):
        return f"{self.id} - {self.item_name} - {self.time}"

    def __hash__(self):
        return int(self.id)

    @property
    def aware_time(self):
        if not self.time:
            return None
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
            RateLimitError
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
            RateLimitError
        """

        url = build_api_url(gacha_type=gacha_type, authkey=self.authkey, lang=self.lang, size=5000)

        data = _api_get(url)

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


class LegacyParser(AbstractParser):
    """
    Parses old db.sqlite from HSR-Warptracker
    """

    def __init__(self, path: str):
        """
        Args:
            path(str): path to the db.sqlite file
        """
        self.path = path

    def fetch(self) -> list[WarpRecord]:
        """
        Reads all warps from the legacy database (read only)

        Returns:
            records(list[WarpRecord]): all warp records, sorted by id

        Raises:
            LegacyFileError
        """
        try:
            with closing(sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(LEGACY_QUERY).fetchall()
        except sqlite3.DatabaseError as e:
            raise LegacyFileError(f"Could not read legacy database: {e}") from e

        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: sqlite3.Row) -> WarpRecord:
        """
        Converts a legacy row to a warp record

        Args:
            row(sqlite3.Row): row of LEGACY_QUERY
        """
        gacha_type = str(row["gacha_type"])
        gacha_id = str(row["gacha_id"])
        if gacha_type == GachaTypes.STELLAR and len(gacha_id) < len(STANDARD_BANNER_ID):
            gacha_id = STANDARD_BANNER_ID

        return WarpRecord(
            id=str(row["warp_id"]).zfill(PULL_ID_LENGTH),
            uid=str(row["uid"]),
            rarity=row["rarity"],
            item_id=str(row["item_id"]),
            item_name=row["name"],
            gacha_type=gacha_type,
            gacha_id=gacha_id,
            time=row["time"],
            time_zone_offset=0,
        )


class PetParser(AbstractParser):
    """
    fetches all pet entries from the api
    """

    def __init__(self, authkey: str, lang: str):
        self.authkey = authkey
        self.lang = lang

    def fetch(self) -> list[PetRecord]:
        uid = self._get_uid()
        records = []
        has_next = True
        max_id = 0
        while has_next:
            dicts, time_offset, max_id = self._fetch_page(max_id)
            has_next = max_id is not None
            for d in dicts:
                records.append(
                    PetRecord(
                        id=d["id"],
                        pool_id=d["pool_id"],
                        item_id=d["item_id"],
                        item_name=d["item_name"],
                        pet_id=d["pet_id"],
                        chroma_appearance_id=str(d["chroma_appearance_id"]),
                        pet_type=d["pet_type"],
                        blind_box_sub_rarity=d["blind_box_sub_rarity"],
                        type_name=d["type_name"],
                        time=d["time"],
                        uid=uid,
                        time_zone_offset=time_offset,
                    )
                )
        return records

    def _fetch_page(self, max_id) -> tuple[dict, int, int]:
        """
        Pulls a single page of pet records

        Returns:
            ret(tuple): dict of pet entries, time_offset, last_id
        """
        parsed = urlparse(PET_API_URL)
        query_dict = parse_qs(parsed.query)

        query_dict["authkey"] = self.authkey
        query_dict["lang"] = self.lang
        query_dict["max_id"] = max_id
        new_query = urlencode(query_dict, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))

        data = _api_get(url)
        entries = data["list"]
        time_offset = data["region_time_zone"]

        entry_dicts = [
            {
                "id": e["id"],
                "pool_id": e["pool_id"],
                "item_id": e["item_id"],
                "item_name": e["item_name"],
                "pet_id": e["pet_id"],
                "chroma_appearance_id": e["chroma_appearance_id"],
                "pet_type": e["pet_type"],
                "blind_box_sub_rarity": e["blind_box_sub_rarity"],
                "type_name": e["type_name"],
                "time": e["time"],
            }
            for e in entries
        ]
        last_id = entries[-1]["id"] if len(entries) == PET_PAGE_SIZE else None
        return entry_dicts, time_offset, last_id

    def _get_uid(self) -> str:
        """
        Calls the warp api and fetches UID from first entry

        Returns:
            uid(str): unique identifier of account
        """
        data = _api_get(build_api_url(gacha_type="1", authkey=self.authkey, lang=self.lang, size=1))
        try:
            entry = data["list"][0]
            return entry["uid"]
        except KeyError as k:
            raise UIDError("Unable to find uid in entry") from k
        except IndexError as i:
            raise UIDError("Returned empty list") from i


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
                banner = self._get_banner(record.gacha_id, record.gacha_type)
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
            new_item = Item.objects.create_from_catalog(entry=entry, name=warp_record.item_name)
            self.items[new_item.item_id] = new_item
            return new_item

    def _get_banner(self, gacha_id: str, gacha_type: str):
        banner = self.banners.get(gacha_id)
        if banner is not None:
            return banner
        else:
            banner = Banner.objects.create(gacha_id=gacha_id, gacha_type=gacha_type)
            self.banners[gacha_id] = banner
            return banner


class PetWriter(AbstractPullWriter):
    """
    Writer for adding pet records to the DB
    """

    def __init__(self):
        self.pets = Pet.objects.in_bulk()
        self.variants = {(v.pet_id, v.chroma_appearance_id): v for v in PetVariant.objects.all()}
        self.pet_pools = PetPool.objects.in_bulk()
        self.pet_types = PetType.objects.in_bulk()

    def write(self, records: list[PetRecord]) -> ImportResult:
        """
        Writes given pet results to DB

        Args:
            records(list): a list of pet records

        Returns:
            result(ImportResult): detailed info about import
        """
        incoming_ids = [x.id for x in records]
        existing_ids = set(PetPull.objects.filter(id__in=incoming_ids).values_list("id", flat=True))
        new_records = [r for r in records if r.id not in existing_ids]

        c_old_variants = len(self.variants)

        pulls = []

        with transaction.atomic():
            for record in new_records:
                pool = self._get_pool(record.pool_id)
                variant = self._get_variant(record)

                pulls.append(
                    PetPull(
                        id=record.id,
                        time=record.aware_time,
                        pool=pool,
                        pet_variant=variant,
                        uid=record.uid,
                    )
                )
            PetPull.objects.bulk_create(pulls)
        return ImportResult(
            created=len(pulls),
            skipped=len(existing_ids),
            new_items=len(self.variants) - c_old_variants,
            unknown_items=set(),  # since no item catalog is used
        )

    def _get_pet_type(self, type_id: str, type_name: str) -> PetType:
        """
        Returns a (new created) pet type

        Args:
            type_id(str): type identifier
            type_name(str): type name

        Returns:
            pet_type(PetType): existing or new created pet type
        """
        pet_type = self.pet_types.get(type_id)
        if pet_type is not None:
            return pet_type
        else:
            new_pet_type = PetType.objects.create(type_id=type_id, type_name=type_name)
            self.pet_types[type_id] = new_pet_type
            return new_pet_type

    def _get_pet(self, record: PetRecord) -> Pet:
        """
        Returns a (new created) pet

        Args:
            record(PetRecord): pet record containing the pulled pet

        Returns:
            pet(Pet): existing or new created pet
        """
        pet_type = self._get_pet_type(type_id=record.pet_type, type_name=record.type_name)
        pet = self.pets.get(record.pet_id)
        if pet is not None:
            if not pet.name and record.chroma_appearance_id == ChromaAppearance.NORMAL:
                pet.name = record.item_name
                pet.save(update_fields=["name"])
            return pet
        else:
            new_pet = Pet.objects.create(
                name=record.item_name
                if str(record.chroma_appearance_id) == ChromaAppearance.NORMAL
                else "",
                pet_id=record.pet_id,
                item_id=record.item_id,
                pet_type=pet_type,
            )
            self.pets[record.pet_id] = new_pet
            return new_pet

    def _get_variant(self, record: PetRecord) -> PetVariant:
        """
        Returns a (new created) pet variant

        Args:
            record(PetRecord): pet record containing the pulled pet variant

        Returns:
            variant(PetVariant): existing or new created pet variant
        """
        pet = self._get_pet(record)
        pet_variant = self.variants.get((pet.pet_id, record.chroma_appearance_id))
        if pet_variant is not None:
            return pet_variant
        else:
            new_pet_variant = PetVariant.objects.create(
                name=record.item_name,
                pet=pet,
                chroma_appearance_id=record.chroma_appearance_id,
                blind_box_sub_rarity=record.blind_box_sub_rarity,
            )
            self.variants[(pet.pet_id, record.chroma_appearance_id)] = new_pet_variant
            return new_pet_variant

    def _get_pool(self, pool_id: str) -> PetPool:
        """
        Returns a (new created) pool object

        Args:
            pool_id(str): pool identifier

        Returns:
            pool(PetPool): pool object
        """
        pool = self.pet_pools.get(pool_id)
        if pool is not None:
            return pool
        else:
            new_pool = PetPool.objects.create(pool_id=pool_id)
            self.pet_pools[pool_id] = new_pool
            return new_pool
