from django import forms
from django.utils.translation import gettext_lazy as _

from .games import all_games


class SettingForm(forms.Form):
    visible_games = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "toggle"}),
        label=_("Visible games"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visible_games"].choices = [(g.game_key, g.verbose_name) for g in all_games()]
