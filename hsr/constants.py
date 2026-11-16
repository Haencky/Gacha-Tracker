from .choices import GachaTypes, ItemTypes

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

HARD_PITYS = {
    GachaTypes.STELLAR: 90,
    GachaTypes.DEPARTURE: 80,
    GachaTypes.CHARACTER_EVENT: 90,
    GachaTypes.LIGHT_CONE_EVENT: 80,
    GachaTypes.CHARACTER_COLLABORATION: 90,
    GachaTypes.LIGHT_CONE_COLLABORATION: 80,
}

FEATURED_TYPES = [
    GachaTypes.CHARACTER_EVENT,
    GachaTypes.CHARACTER_COLLABORATION,
    GachaTypes.LIGHT_CONE_EVENT,
    GachaTypes.LIGHT_CONE_COLLABORATION,
]

ITEM_TYPES = {
    GachaTypes.STELLAR: ItemTypes.CHARACTER,
    GachaTypes.DEPARTURE: ItemTypes.CHARACTER,
    GachaTypes.CHARACTER_EVENT: ItemTypes.CHARACTER,
    GachaTypes.CHARACTER_COLLABORATION: ItemTypes.CHARACTER,
    GachaTypes.LIGHT_CONE_EVENT: ItemTypes.LIGHT_CONE,
    GachaTypes.LIGHT_CONE_COLLABORATION: ItemTypes.LIGHT_CONE,
}
