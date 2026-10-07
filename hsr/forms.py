from urllib.parse import parse_qs, urlparse

from django import forms


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
            raise forms.ValidationError("No authkey provided")

        return authkey, lang
