from django.conf import settings

from .games import visible_games


def games(request):
    match = request.resolver_match
    return {
        "games": visible_games(),
        "current_game": match.namespace if match else None,
    }


def app_info(request):
    return {"version": settings.APP_VERSION}
