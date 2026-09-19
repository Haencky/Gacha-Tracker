from django.shortcuts import render


# Create your views here.
def index(request):
    return render(request, "core/index.html")


def import_view(request):
    # Platzhalter – der echte Import kommt mit Issue #7
    return render(request, "core/import.html")
