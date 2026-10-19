from urllib.parse import parse_qs, urlparse

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _


class ImportUrlForm(forms.Form):
    url = forms.CharField()

    def clean_url(self) -> tuple[str, str]:
        """
        Takes the url and returns the language code and the auth key

        Returns:
            components(tuple[str, str]): authkey and language code
        """
        parsed = urlparse(self.cleaned_data["url"])
        query_dict = parse_qs(parsed.query)

        lang = query_dict.get("lang", ["en"])[0]
        authkey = query_dict.get("authkey", [None])[0]

        if not authkey:
            raise forms.ValidationError(_("No authkey provided"))

        return authkey, lang


class ImportFileForm(forms.Form):
    file = forms.FileField()

    def clean_file(self) -> UploadedFile:
        f = self.cleaned_data["file"]
        begin = f.read(16)
        f.seek(0)

        if begin != b"SQLite format 3\x00":
            raise forms.ValidationError(_("Invalid db file"))
        return f


class AddItemForm(forms.Form):
    item_id = forms.CharField()
