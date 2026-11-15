from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


# Create your views here.
def index(request):
    """
    Index page displaying all games
    """
    return render(request, "core/index.html")


def _has_users() -> bool:
    return get_user_model().objects.exists()


class LoginView(auth_views.LoginView):
    """
    Login page, sends the visitor to the setup page as long as no account exists
    """

    # get() instead of dispatch(): the parent decorates dispatch with login_not_required,
    # overriding it would drop that marker and LoginRequiredMiddleware would loop on /login
    def get(self, request, *args, **kwargs):
        if not _has_users():
            return redirect("setup")
        return super().get(request, *args, **kwargs)


@login_not_required
def setup(request):
    """
    First run setup, creates the admin account. Only reachable while no user exists
    """
    if _has_users():
        return redirect("login")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        # check again, another request could have created the account in the meantime
        if form.is_valid() and not _has_users():
            user = form.save(commit=False)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            login(request, user)
            return redirect("/")
    else:
        form = UserCreationForm()

    return render(request, "registration/setup.html", {"form": form})
