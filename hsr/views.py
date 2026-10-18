# Create your views here.
import os
from tempfile import NamedTemporaryFile

from django.contrib import messages
from django.db.models import Count, F, Min, Q
from django.db.models.functions import Least
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from core.services.stats import Stats, get_stats

from .choices import FiftyFifty, GachaTypes, ItemTypes
from .constants import FEATURED_TYPES, HARD_PITYS, ITEM_TYPES
from .exceptions import (
    ApiError,
    AuthkeyError,
    AuthkeyTimeoutError,
    FileError,
    ItemCatalogItemDoesNotExistError,
)
from .forms import ImportFileForm, ImportUrlForm
from .importer import ApiParser, ItemCatalog, LegacyParser, RecordWriter
from .models import Banner, Item, Path, Warp
from .services import assign_featured_items, download_missing_images, recalculate_pity


def _finish_import(request, result):
    if result.created == 0:
        return
    messages.success(
        request,
        _(f"Imported {result.created}, New items: {result.new_items}"),
    )

    if result.unknown_items:
        messages.warning(request, f"Unknown items: {result.unknown_items}")
    assignment = assign_featured_items()
    recalculate_pity()
    if assignment.success:
        messages.success(request, _(f"Successfully assigned {assignment.success} items"))
    if assignment.fail:
        messages.error(request, _(f"Failed to assign {assignment.fail} items"))
    donwload = download_missing_images()
    if s_icons := donwload.item_icons.success:
        messages.success(request, _(f"Downloaded {s_icons} icons"))
    if f_icons := donwload.item_icons.fail:
        messages.error(request, _(f"Failed to download {f_icons} icons"))
    if s_portraits := donwload.item_portraits.success:
        messages.success(request, _(f"Downloaded  {s_portraits} portraits"))
    if f_portraits := donwload.item_portraits.fail:
        messages.error(request, _(f"Failed to download {f_portraits} portraits"))
    if s_dtypes := donwload.dtype.success:
        messages.success(request, _(f"Dpwnloaded {s_dtypes} damage type icons"))
    if f_dtype := donwload.dtype.fail:
        messages.error(request, _(f"Failed to download {f_dtype} damage type icons"))
    if s_path := donwload.path.success:
        messages.success(request, _(f"Downloaded {s_path} path icons"))
    if f_path := donwload.path.fail:
        messages.error(request, _(f"Failed to download {f_path} path icons"))


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
            try:
                writer = RecordWriter(ItemCatalog.load())
                result = writer.write(parser.fetch())
            except AuthkeyTimeoutError:
                messages.error(request, _("Authkey is too old"))
            except AuthkeyError:
                messages.error(request, _("Invalid authkey"))
            except ApiError:
                messages.error(request, _("Failed to connect to the API"))
            except ItemCatalogItemDoesNotExistError as e:
                messages.error(request, str(e))
            else:
                _finish_import(request, result)
                return redirect("hsr:index")
            return _render_import(request, url_form=form, active_tab="api")
        else:
            return _render_import(request, url_form=form, active_tab="api")

    else:
        form = ImportUrlForm()
        return _render_import(request, url_form=form, active_tab="api")


def import_file(request):
    """
    Takes file (UIGF, legacy db, Star Rail Station)
    """
    if request.method == "POST":
        form = ImportFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data["file"]
            tmp = NamedTemporaryFile(suffix=".sqlite3", delete=False)
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp.close()
            try:
                result = RecordWriter(ItemCatalog.load()).write(LegacyParser(tmp.name).fetch())
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
        Item.objects.annotate(pulls=Count("warps")).select_related("damage_type", "path"),
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
