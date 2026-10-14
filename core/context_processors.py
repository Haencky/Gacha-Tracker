from .games import all_games


def games(request):
    return {
        "games": all_games(),
        "current_game": request.resolver_match.namespace
        if request.resolver_match.namespace
        else None,
    }
