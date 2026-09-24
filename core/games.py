from django.apps import apps


def all_gamaes():
    """
    Return all games identified by their game key (normally the UIGF Key)
    """
    return [c for c in apps.get_app_configs() if getattr(c, "game_key", None)]


def by_uigf_key(key: str):
    """
    Return specific game identified by given key

    Args:
        key(str): str to identify the game
    """
    return next((c for c in all_gamaes() if c.game_key == key), None)
