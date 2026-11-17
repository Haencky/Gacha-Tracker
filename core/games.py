from django.apps import apps


def all_games():
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
    return next((c for c in all_games() if c.game_key == key), None)


def game_summary():
    return [c.summary() for c in all_games()]


def hidden_game_keys() -> set[str]:
    """Return the game_keys of all games hidden in the settings."""
    from .models import GameSettings

    return set(GameSettings.objects.filter(visible=False).values_list("game_key", flat=True))


def visible_games():
    """Return all games that are not hidden in the settings."""
    hidden = hidden_game_keys()
    return [g for g in all_games() if g.game_key not in hidden]
