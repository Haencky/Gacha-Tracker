import requests

from core.importer import AbstractParser, AbstractPullRecord

from .choices import GachaTypes

UIGF_API = "https://api.uigf.org/translate/"
# lang: lang
# type: "normal" (name -> item_id)
# game: "genshin"
# item_name: item_name

GAME_DATA_URL = "https://gi.yatta.moe/api/v2/en/{item_type}/{item_id}"
IMAGE_URL = "https://gi.yatta.moe/assets/UI/{icon}.png"  # icon is defined in GAME_DATA_URL response
HOYO_API = "https://public-operation-hk4e-sg.hoyoverse.com/gacha_info/api/getGachaLog?authkey_ver=1&sign_type=2&lang={lang}&authkey={auth_key}&game_biz=hk4e_global&gacha_type={gacha_type}&size=5&end_id={end_id}"


# Support Classes
class ItemRecord:
    """
    Support class for items

    Attributes:
        name(str): item name
        item_id(str): item id
        img_link(str): link to image
        weapon(str): weapon type
    """

    def __init__(
        self,
        name: str,
        item_id,
        img_link: str,
        weapon: str = None,
    ):
        self.name = name
        self.item_id = item_id
        self.img_link = img_link
        self.weapon = weapon


class WishRecord(AbstractPullRecord):
    """
    Custom object for wish records

    Attributes:
        id(str): pull identifier
        uid(str): account identifier
        time(str): timestamp
        name(str): item name
        item_type(str): weapon type
        rank_type(str): rarity
    """

    def __init__(self, id: str, uid: str, time: str, name: str, item_type: str, rank_type: str):
        self.id = id
        self.uid = uid
        self.time
        self.name = name
        self.item_type = item_type
        self.rank_type = rank_type


def get_item_id(name: str, lang: str = "en") -> str:
    """
    Returns the ID of a given item name

    Args:
        name(str): item name
        lang(str): language

    Returns:
        id(str): item id
    """
    paylaod = {"type": "normal", "game": "genshin", "item_name": name, "lang": lang}

    try:
        response = requests.post(UIGF_API, json=paylaod, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        print("TODO")  # TODO: exception handling

    try:
        j = response.json()
        return j["item_id"]
    except KeyError:
        print("TODO")  # TODO: exception handling


def get_item_info(item_id: str) -> ItemRecord:
    """
    Fetches game info of given item

    Args:
        item_id(str): item id

    Returns:
        record(ItemRecord): information about item
    """

    item_type = "avatar" if item_id >= 10000000 else "weapon"
    url = GAME_DATA_URL.format(item_type=item_type, item_id=item_id)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        print("TODO")  # TODO: exception handling

    try:
        data = response.json()["data"]
    except KeyError:
        print("TODO")  # TODO: exception handling

    return ItemRecord(
        name=data["name"], item_id=data["id"], img_link=data["icon"], weapon=data["weaponType"]
    )


class GenshinApiParser(AbstractParser):
    """
    Genshin API parser

    Params:
        authkey(str)
        lang(str): language used
    """

    def __init__(self, authkey: str, lang: str):
        self.authkey = authkey
        self.lang = lang

    def fetch(self) -> list[WishRecord]:
        for g in GachaTypes:
            self._fetch_gacha_type(g)

    def _fetch_gacha_type(self, gacha_type: int):
        """
        Fetches pull history for given gacha_type

        Args:
            gacha_type(int): given gacha type
        """
        has_next = True
        end_id = 0
        while has_next:
            has_next, end_id, records = self._fetch_page(gacha_type, end_id)
