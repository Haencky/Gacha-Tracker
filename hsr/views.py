# Create your views here.
import logging
import os
from tempfile import NamedTemporaryFile

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, F, Max, Min, Q, Sum
from django.db.models.functions import Least
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views import generic

from core.services.stats import Stats, get_stats

from .choices import FiftyFifty, GachaTypes, ItemTypes
from .constants import CELESTIAL_INVITES, FEATURED_TYPES, HARD_PITYS, ITEM_TYPES
from .exceptions import (
    ApiError,
    AuthkeyError,
    AuthkeyTimeoutError,
    FileError,
    ItemCatalogItemDoesNotExistError,
    RateLimitError,
    UIDError,
)
from .forms import AddItemForm, BannerEditForm, ImportFileForm, ImportUrlForm
from .importer import (
    ApiParser,
    ImportResult,
    ItemCatalog,
    LegacyParser,
    PetParser,
    PetWriter,
    RecordWriter,
)
from .models import Banner, Item, Path, PetType, PetVariant, Warp
from .services import assign_featured_items, download_missing_images, recalculate_pity

logger = logging.getLogger(__name__)


def _finish_import(request, result: ImportResult):
    if result.created > 0:
        messages.success(
            request,
            _("Imported pulls: %(created)d, New items: %(items)d")
            % {"created": result.created, "items": result.new_items},
        )
    if result.unknown_items:
        messages.warning(request, _("Unknown items: %(count)d") % {"count": result.unknown_items})
    assignment = assign_featured_items()
    recalculate_pity()
    if assignment.success:
        messages.success(
            request,
            ngettext(
                "Successfully assigned %(items)d item",
                "Successfully assigned %(items)d items",
                assignment.success,
            )
            % {"items": assignment.success},
        )
    if assignment.fail:
        messages.warning(
            request,
            ngettext(
                "Failed to assign %(items)d item",
                "Failed to assign %(items)d items",
                assignment.fail,
            )
            % {"items": assignment.fail},
        )
    donwload = download_missing_images(
        catalog=cache.get_or_set("hsr_item_catalog", ItemCatalog.load, 3600)
    )
    failed = 0
    failed += donwload.dtype.fail
    failed += donwload.path.fail
    failed += donwload.item_portraits.fail
    failed += donwload.item_icons.fail

    if failed > 0:
        messages.warning(
            request,
            ngettext(
                "Failed to download %(count)d image. See logs for details.",
                "Failed to download %(count)d images. See logs for details.",
                failed,
            )
            % {"count": failed},
        )


def _render_import(
    request,
    url_form: ImportUrlForm = None,
    file_form: ImportFileForm = None,
    active_tab: str = "api",
):
    """
    Support function for rendering the import forms
    """
    return render(
        request,
        "hsr/import.html",
        {
            "url_form": url_form or ImportUrlForm(),
            "file_form": file_form or ImportFileForm(),
            "active_tab": active_tab,
        },
    )


def index(request):
    types = []
    for t in GachaTypes:
        warps = (
            Warp.objects.filter(gacha_type=t)
            .select_related("item", "banner__featured_item")
            .order_by("id")
        )
        stat: Stats = get_stats(warps, t in FEATURED_TYPES)
        types.append(
            {
                "label": t.label,
                "max_pity": HARD_PITYS[t],
                "count": stat.count,
                "guaranteed": stat.guaranteed,
                "last_win": stat.last_win,
                "current_pity": stat.current_pity,
                "success": stat.success_50_50,
                "attempts_50_50": stat.attempts_50_50,
                "winrate": round(stat.success_50_50 / stat.attempts_50_50, 2) * 100
                if stat.attempts_50_50
                else None,
                "expected_pity": round(stat.expected_pity, 2) if stat.expected_pity else None,
                "jade": stat.count * 160,
                "euro": round(stat.count * 2.64, 2),
                "item_type": ITEM_TYPES[t],
            }
        )

    return render(request, "hsr/index.html", {"types": types})


def import_api_view(request):

    if request.method == "POST":
        form = ImportUrlForm(request.POST)
        if form.is_valid():
            authkey, lang = form.cleaned_data["url"]
            parser = ApiParser(authkey=authkey, lang=lang)
            pet_parser = PetParser(authkey=authkey, lang=lang)
            try:
                writer = RecordWriter(cache.get_or_set("hsr_item_catalog", ItemCatalog.load, 3600))
                result = writer.write(parser.fetch())
            except RateLimitError:
                messages.error(request, _("Visited too frequently"))
                logger.warning("Visited too frequently")
            except AuthkeyTimeoutError:
                messages.warning(request, _("Authkey is too old"))
            except AuthkeyError:
                messages.warning(request, _("Invalid authkey"))
            except ApiError as e:
                messages.error(request, f"{e.retcode} ({str(e)})")
                logger.exception("API error %s:%s", e.retcode, e)
            else:
                _finish_import(request, result)

            try:
                pet_writer = PetWriter()
                pet_result = pet_writer.write(pet_parser.fetch())
            except RateLimitError:
                messages.error(request, _("Visited too frequently"))
                logger.exception("Visited to frequently")
            except AuthkeyTimeoutError:
                messages.error(request, _("Authkey is too old"))
                logger.warning("Provided authkey is too old")
            except AuthkeyError:
                messages.error(request, _("Invalid authkey"))
                logger.warning("Provided authkey is invalid")
            except ApiError as e:
                messages.error(request, _("Failed to connect to the API"))
                logger.exception("Failed to connect to the API %s:%s", e.retcode, str(e))
            except UIDError:
                messages.error(request, _("Unable to fetch UID"))
                logger.exception("Unable to get UID from pull history")
            else:
                if pet_result.created > 0:
                    messages.success(
                        request,
                        _("Created pets: %(new_items)d") % {"new_items": pet_result.new_items},
                    )
                    messages.success(
                        request,
                        _("Imported pet pulls: %(created)d") % {"created": pet_result.created},
                    )
                return redirect("hsr:index")
            return _render_import(request, url_form=form, active_tab="api")
        else:
            return _render_import(request, url_form=form, active_tab="api")

    else:
        form = ImportUrlForm()
        return _render_import(request, url_form=form, active_tab="api")


def import_file(request):
    """
    Takes file (UIGF, legacy db)
    """
    if request.method == "POST":
        form = ImportFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data["file"]
            with NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
            try:
                result = RecordWriter(
                    cache.get_or_set("hsr_item_catalog", ItemCatalog.load, 3600)
                ).write(LegacyParser(tmp.name).fetch())
            except FileError:
                messages.error(request, _("File could not be read"))
            else:
                _finish_import(request, result)
                return redirect("hsr:index")
            finally:
                os.remove(tmp.name)
            return _render_import(request, file_form=form, active_tab="file")

        else:
            return _render_import(request, file_form=form, active_tab="file")
    else:
        form = ImportFileForm()
        return _render_import(request, file_form=form, active_tab="file")


def search_item(request):
    """
    Searches for items
    """
    query = request.GET.get("q", "")
    items = Item.objects.filter(Q(name__icontains=query) | Q(eng_name__icontains=query))
    items = items.order_by("-rarity", "name")
    if not query:
        items = None

    return render(request, "hsr/partials/item_menu.html", {"items": items})


def detail_item(request, item_id: str):
    """
    Returns detailed information about given item

    Args:
        item_id(str): unique item identifier
    """

    item = get_object_or_404(
        Item.objects.annotate(pulls=Count("warps"))
        .annotate(featured_pulls_total=Sum(F("warps__featured_pity")))
        .select_related("damage_type", "path"),
        item_id=item_id,
    )
    warps = item.warps.order_by("-id")
    count = len(warps)
    eidolon = min(count - 1, 6)
    lvl = min(count, 5)

    return render(
        request,
        "hsr/item_detail.html",
        {"item": item, "warps": warps, "count": count, "eidolon": eidolon, "lvl": lvl},
    )


def overview_item(request):
    """
    Overview of all obtained items
    """
    rar = request.GET.getlist("rarity")
    path = request.GET.getlist("path")
    types = request.GET.getlist("type")
    items = (
        Item.objects.select_related("path", "damage_type")
        .all()
        .annotate(pulls=Count("warps"))
        .annotate(eidolon=Least(F("pulls") - 1, 6), lvl=Least(F("pulls"), 5))
        .order_by("-rarity", "-pulls", "item_type", "name")
    )

    if rar:
        items = items.filter(rarity__in=rar)
    if path:
        items = items.filter(path__in=path)
    if types:
        items = items.filter(item_type__in=types)
    paths = Path.objects.order_by("name")
    rarities = Item.objects.values_list("rarity", flat=True).distinct().order_by("-rarity")

    return render(
        request,
        "hsr/item_overview.html",
        {
            "items": items,
            "paths": paths,
            "rarities": rarities,
            "item_types": ItemTypes.choices,
            "selected_rarities": [int(r) if r.isdigit() else r for r in rar],
            "selected_paths": [int(p) for p in path],
            "selected_types": types,
        },
    )


def overview_banner(request, gacha_type: str):
    """
    Overview about all pulled banner
    """
    available = set(Warp.objects.order_by().values_list("gacha_type", flat=True).distinct())
    tabs = [t for t in GachaTypes if t in available and t in FEATURED_TYPES]
    if gacha_type not in GachaTypes.values:
        raise Http404
    banner = (
        Banner.objects.select_related("featured_item")
        .filter(gacha_type=gacha_type)
        .annotate(
            pulls=Count("warps"),
            first_pull=Min("warps__id"),
            featured_pulls=Count("warps", filter=Q(warps__item=F("featured_item"))),
            lost=Count("warps", filter=Q(warps__fifty_fifty=FiftyFifty.LOST)),
        )
        .order_by("-first_pull")
    )
    return render(
        request,
        "hsr/banner_overview.html",
        {
            "banner": banner,
            "tabs": tabs,
            "item_type": ITEM_TYPES[gacha_type],
            "gacha_type": gacha_type,
        },
    )


def _distribution(counts: list[tuple[int, int]], total: int) -> list[dict]:
    """
    Builds the segments of the stacked rarity bar

    Args:
        counts(list[tuple[int, int]]): rarity and count pairs
        total(int): total pulls

    Returns:
        segments(list[dict]): rarity, count, x offset and width in percent
    """
    segments = []
    offset = 0
    for rarity, count in counts:
        width = count / total * 100
        segments.append({"rarity": rarity, "count": count, "x": offset, "width": width})
        offset += width
    return segments


def detail_banner(request, banner_id):
    """
    Detailed information about a banner, its warps and obtained items

    Args:
        banner_id(str): gacha id of the banner
    """
    four = Q(warps__item__rarity=4)
    banner = get_object_or_404(
        Banner.objects.select_related("featured_item").annotate(
            pulls=Count("warps"),
            five=Count("warps", filter=Q(warps__item__rarity=5)),
            four=Count("warps", filter=four),
            four_characters=Count(
                "warps", filter=four & Q(warps__item__item_type=ItemTypes.CHARACTER)
            ),
            four_light_cones=Count(
                "warps", filter=four & Q(warps__item__item_type=ItemTypes.LIGHT_CONE)
            ),
            featured_pulls=Count("warps", filter=Q(warps__item=F("featured_item"))),
            lost=Count("warps", filter=Q(warps__fifty_fifty=FiftyFifty.LOST)),
            first_time=Min("warps__time"),
            last_time=Max("warps__time"),
        ),
        gacha_id=banner_id,
    )
    warps = list(banner.warps.select_related("item").order_by("-id"))
    items = (
        Item.objects.filter(warps__banner=banner, rarity__gte=4)
        .annotate(obtained=Count("warps"))
        .order_by("-rarity", "-obtained", "name")
    )
    three = banner.pulls - banner.five - banner.four
    total = banner.pulls or 1

    return render(
        request,
        "hsr/banner_detail.html",
        {
            "banner": banner,
            "item_type": ITEM_TYPES[banner.gacha_type],
            "has_50_50": banner.gacha_type in FEATURED_TYPES,
            "warps": warps,
            "items": items,
            "five_pities": [w.pity for w in reversed(warps) if w.item.rarity == 5],
            "distribution": _distribution([(5, banner.five), (4, banner.four), (3, three)], total),
        },
    )


def _add_candidate(catalog: ItemCatalog, q="") -> list:
    items = catalog.all()
    existing = set(Item.objects.values_list("item_id", flat=True))
    items = [i for i in items if i["item_id"] not in existing and not i["unreleased"]]
    if q:
        items = [
            item for item in items if q.lower() in item["name"].lower() and not item["unreleased"]
        ]

    return sorted(items, key=lambda x: x["name"])


def add_item(request):
    """
    Adds item manually
    """
    catalog = cache.get_or_set("hsr_item_catalog", ItemCatalog.load, 3600)
    items = _add_candidate(catalog)
    form = AddItemForm()

    if request.method == "POST":
        form = AddItemForm(request.POST)
        if form.is_valid():
            item_id = form.cleaned_data["item_id"]

            if Item.objects.filter(item_id=item_id).exists():
                messages.warning(request, _("Item already exists"))
            else:
                try:
                    entry = catalog.get(item_id)
                except ItemCatalogItemDoesNotExistError:
                    messages.error(request, _("Item does not exist"))
                    return redirect("hsr:item-add")
                Item.objects.create_from_catalog(entry, entry.eng_name)
                download_missing_images(catalog)

                return redirect("hsr:item-detail", item_id=item_id)

    return render(request, "hsr/item_add.html", {"items": items, "form": form})


def add_search_item(request):
    catalog = cache.get_or_set("hsr_item_catalog", ItemCatalog.load, 3600)
    q = request.GET.get("q", "")

    items = _add_candidate(catalog, q)

    return render(request, "hsr/partials/item_add_candidate.html", {"items": items})


def overview_pet(request, type_id: str):
    tabs = PetType.objects.all()

    pets = (
        PetVariant.objects.all()
        .select_related("pet", "pet__pet_type")
        .filter(pet__pet_type=type_id)
        .annotate(count=Count("pulls"))
        .order_by("name", "-count", "chroma_appearance_id")
    )

    return render(
        request, "hsr/pet_overview.html", {"pets": pets, "tabs": tabs, "pet_type": type_id}
    )


class EditBanner(generic.edit.UpdateView):
    model = Banner
    form_class = BannerEditForm
    template_name = "hsr/partials/banner_edit_view.html"

    def form_valid(self, form):
        self.object = form.save()
        recalculate_pity()
        response = HttpResponse()
        response["HX-Refresh"] = "true"
        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields["featured_item"].queryset = (
            Item.objects.filter(rarity=5, item_type=ITEM_TYPES[self.object.gacha_type])
            .exclude(item_id__in=CELESTIAL_INVITES)
            .order_by("name")
        )
        return form
