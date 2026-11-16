from django.apps import AppConfig


class HsrConfig(AppConfig):
    name = "hsr"
    game_key = "hkrpg"
    verbose_name = "Honkai: Star Rail"
    slug = "hsr"
    url_name = "hsr:index"

    def summary(self):
        from .models import Warp

        return Warp.objects.all().count()
