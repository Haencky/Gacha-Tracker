import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_renders(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_import_page_renders(client):
    response = client.get(reverse("core:import"))

    assert response.status_code == 200
