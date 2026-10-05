from django.shortcuts import render

from .games import all_games


# Create your views here.
def index(request):
    """
    Index page displaying all games
    """
    return render(request, "core/index.html", {"games": all_games()})
