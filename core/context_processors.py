from django.conf import settings

from .games import all_games


def games(request):
    return {
        "games": all_games(),
        "current_game": request.resolver_match.namespace
        if request.resolver_match.namespace
        else None,
    }


def app_info(request):
    return {"version": settings.APP_VERSION}
