import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.test.utils import isolate_apps
from django.urls import reverse
from django.utils import timezone

from core.models import AbstractItem, AbstractPull

PULL_ID = "1683000000000000001"


@pytest.mark.django_db
def test_home_page_renders(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_import_page_renders(client):
    response = client.get(reverse("core:import"))

    assert response.status_code == 200


# Issue #3 - abstract base models for game apps


@pytest.fixture
def game_models(transactional_db):
    """Two concrete models standing in for two game apps, with real tables.

    Separate concrete models get separate tables, which is what lets the same
    HoYoverse pull ID exist in more than one game.
    """
    with isolate_apps("core"):

        class AlphaPull(AbstractPull):
            class Meta:
                app_label = "core"

        class BetaPull(AbstractPull):
            class Meta:
                app_label = "core"

        with connection.schema_editor() as editor:
            editor.create_model(AlphaPull)
            editor.create_model(BetaPull)
        try:
            yield AlphaPull, BetaPull
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(BetaPull)
                editor.delete_model(AlphaPull)


def test_core_contributes_no_tables():
    """Migrations for the core app contain no game-specific tables."""
    assert AbstractPull._meta.abstract
    assert AbstractItem._meta.abstract
    assert list(apps.get_app_config("core").get_models()) == []


def test_game_app_can_subclass_the_bases():
    """A game app can define concrete models by subclassing these bases."""
    with isolate_apps("core"):

        class Pull(AbstractPull):
            class Meta:
                app_label = "core"

        class Item(AbstractItem):
            class Meta:
                app_label = "core"

        assert Pull.check() == []
        assert Item.check() == []
        assert {f.name for f in Pull._meta.fields} == {"id", "uid", "gacha_type", "time"}
        assert {"item_id", "name", "rarity"} <= {f.name for f in Item._meta.fields}


def test_pull_id_is_the_primary_key():
    """The 19-digit HoYoverse ID is the natural key, so it is unique per game."""
    with isolate_apps("core"):

        class Pull(AbstractPull):
            class Meta:
                app_label = "core"

        assert Pull._meta.pk.name == "id"
        assert Pull._meta.pk.get_internal_type() == "CharField"


def test_same_pull_id_can_exist_in_two_games(game_models):
    alpha, beta = game_models
    now = timezone.now()

    alpha.objects.create(id=PULL_ID, uid="800000001", gacha_type="11", time=now)
    beta.objects.create(id=PULL_ID, uid="700000001", gacha_type="301", time=now)

    assert alpha.objects.filter(pk=PULL_ID).exists()
    assert beta.objects.filter(pk=PULL_ID).exists()


def test_pull_id_is_unique_within_one_game(game_models):
    alpha, _ = game_models
    now = timezone.now()

    alpha.objects.create(id=PULL_ID, uid="800000001", gacha_type="11", time=now)

    with pytest.raises(IntegrityError), transaction.atomic():
        alpha.objects.create(id=PULL_ID, uid="800000002", gacha_type="11", time=now)


def test_pull_time_is_stored_timezone_aware(game_models):
    alpha, _ = game_models

    alpha.objects.create(id=PULL_ID, uid="800000001", gacha_type="11", time=timezone.now())

    assert alpha.objects.get(pk=PULL_ID).time.tzinfo is not None
