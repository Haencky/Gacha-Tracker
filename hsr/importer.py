from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from core.importer import AbstractParser, AbstractPullRecord

from .exceptions import ApiConnectionError, AuthkeyError, AuthkeyTimeoutError, GachaTypeError
from .models import GachaTypes, ItemTypes

IMAGE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
# icons for paths are icon/path/{Pathname}.png (capital)
# icons for elements are icon/element/{Element}.png (capital)
# icons for characters are icon/character/{Item_ID}.png
# images for characters are image/character_preview/{Item_ID}.png
# images for light cones are image/light_cone_portrait/{Item_ID}.png
# full arts for characters are image/character_portrait/{Item_ID}.png
API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global&size=5000"
# authkey_ver=1
# sign_type=2
# lang={lang}
# size=10_000
# gacha_type={gacha type}
# authkey={authkey}
# game_biz=hkrpg_global
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
