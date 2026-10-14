from django.shortcuts import render


# Create your views here.
def index(request):
    """
    Index page displaying all games
    """
    return render(request, "core/index.html")
