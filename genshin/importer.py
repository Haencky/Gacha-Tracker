UIGF_API = "https://api.uigf.org/translate/"
# lang: lang
# type: "normal" (name -> item_id)
# game: "genshin"
# item_name: item_name

GAME_DATA_URL = "https://gi.yatta.moe/api/v2/en/{item_type}/{item_id}"
IMAGE_URL = "https://gi.yatta.moe/assets/UI/{icon}.png"  # icon is defined in GAME_DATA_URL response
HOYO_API = "https://public-operation-hk4e-sg.hoyoverse.com/gacha_info/api/getGachaLog?authkey_ver=1&sign_type=2&lang={lang}&authkey={auth_key}&game_biz=hk4e_global&gacha_type={gacha_type}&size=5&end_id={end_id}"
