# Create your views here.
from django.contrib import messages
from django.db.models import Count, F, Q
from django.db.models.functions import Least
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from core.services.stats import Stats, get_stats

from .choices import GachaTypes
from .constants import FEATURED_TYPES, HARD_PITYS
from .forms import ImportUrlForm
from .models import Item, Warp


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
            }
        )

    return render(request, "hsr/index.html", {"types": types})


def import_api_view(request):
    from .exceptions import (
        ApiError,
        AuthkeyError,
        AuthkeyTimeoutError,
        ItemCatalogItemDoesNotExistError,
    )
    from .importer import ApiParser, ItemCatalog, RecordWriter
    from .services import assign_featured_items, download_missing_images

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
                messages.error(request, e.message)
            else:
                messages.success(
                    request,
                    _(f"Imported {result.created}, New items: {result.new_items}"),
                )
                if result.unknown_items:
                    messages.warning(request, f"Unknown items: {result.unknown_items}")
                assignment = assign_featured_items()
                if assignment.success:
                    messages.success(
                        request, _(f"Successfully assigned {assignment.success} items")
                    )
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
                return redirect("hsr:index")
        else:
            return render(request, "hsr/import_api.html", {"form": form})

    else:
        form = ImportUrlForm()
        return render(request, "hsr/import_api.html", {"form": form})
    return redirect("hsr:index")


def search_item(request):
    """
    Searches for items
    """
    query = request.GET.get("q", "")
    items = (
        Item.objects.filter(Q(name__icontains=query) | Q(eng_name__icontains=query))
        .annotate(pulls=Count("warps"))
        .annotate(eidolon=Least(F("pulls") - 1, 6), lvl=Least(F("pulls"), 5))
    )
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

    item = get_object_or_404(Item, item_id=item_id)
    warps = item.warps.order_by("-time")
    count = len(warps)
    eidolon = min(count - 1, 6)
    lvl = min(count, 5)

    return render(
        request,
        "hsr/item_detail.html",
        {"item": item, "warps": warps, "count": count, "eidolon": eidolon, "lvl": lvl},
    )
