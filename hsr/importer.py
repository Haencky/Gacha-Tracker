from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from core.importer import AbstractParser, AbstractPullRecord

from .exceptions import ApiConnectionError, AuthkeyError
from .models import ItemTypes

IMAGE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
# icons for paths are icon/path/{Pathname}.png (capital)
# icons for elements are icon/element/{Element}.png (capital)
# icons for characters are icon/character/{Item_ID}.png
# images for characters are image/character_preview/{Item_ID}.png
# images for light cones are image/light_cone_portrait/{Item_ID}.png
# full arts for characters are image/character_portrait/{Item_ID}.png
API_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/hkrpg_gacha_record/api/getGachaLog?authkey_ver=1&sign_type=2&game_biz=hkrpg_global&size=10000"
# authkey_ver=1
# sign_type=2
# lang={lang}
# size=10_000
# gacha_type={gacha type}
# authkey={authkey}
# game_biz=hkrpg_global


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

    @classmethod
    def from_api(self, entry: dict, tz_offset: int) -> None:
        """
        Builds custom warp object based on HoYos API answer

        Args:
            entry(dict): single record entry
            tz_offset(int): offset from utc time
        """


class ApiParser(AbstractParser):
    def __init__(self, authkey: str):
        self.authkey = authkey

    def fetch(self):
        pass

    def fetch_gacha_type(self, gacha_type: str) -> list[WarpRecord]:
        """
        Fetches all entries for given gacha_type from HoYos API

        Args:
            authkey(str): short time authentication token to for requesting API infos
            gacha_type(str): gacha type to be fetched

        Returns:
            records(list[WarpRecord]): list of all warp records
        """
        parsed = urlparse(API_URL)
        query_dict = parse_qs(parsed.query)

        query_dict["gacha_type"] = [gacha_type]
        query_dict["authkey"] = [self.authkey]
        new_query = urlencode(query_dict, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))

        try:
            response = requests.get(url, timeout=10)
            if not response.status_code == 200:  # http code not "OK"
                raise ApiConnectionError()
            j = response.json()
            if j["retcode"] != 0:  # http ok, but retcode not ok
                raise AuthkeyError(j["message"])
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
