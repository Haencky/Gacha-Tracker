from core.stats import Stats, get_stats

from .choices import GachaTypes
from .constants import FEATURED_TYPES, HARD_PITYS
from .models import Warp


# Create your views here.
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
                "winrate": stat.winrate,
                "expected_pity": stat.expected_pity,
            }
        )
