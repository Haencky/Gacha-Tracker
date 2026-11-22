from django.db import models
from django.utils.translation import gettext_lazy as _


class FiftyFifty(models.TextChoices):
    WON = "Won", _("Won")
    LOST = "Lost", _("Lost")
    GUARANTEED = "Guaranteed", _("Guaranteed")
    NONE = "", _("-")
