from dataclasses import dataclass

from ..models import AbstractItem, AbstractPull


@dataclass
class Stats:
    count: int
    guaranteed: bool
    last_win: AbstractItem | None
    current_pity: int
    success_50_50: int | None
    attempts_50_50: int | None
    expected_pity: float | None


def get_stats(pulls: list[AbstractPull], has_50_50: bool = True) -> Stats:
    """
    Returns information of given abstract pulls

    Args:
        pulls(list[AbstractPull]): a list of sorted concrete pull objects
        has_50_50(bool): true if pulls can contain non limited characters and limited characters

    Returns:
        stats(Stats): stats about the given pulls
    """

    pity = 0
    win_pity = 0
    guaranteed = False
    won_50_50 = []
    won_pitys = []
    last_win: AbstractItem = None

    for p in pulls:
        pity += 1
        win_pity += 1
        if p.is_highest_rank:
            lost = p.is_lost
            if has_50_50 and not guaranteed:
                won_50_50.append(not lost)
            guaranteed = lost
            if not lost:
                won_pitys.append(win_pity)
                last_win = p.item
                win_pity = 0
            pity = 0

    return Stats(
        count=len(pulls),
        guaranteed=guaranteed,
        last_win=last_win,
        current_pity=pity,
        success_50_50=sum(won_50_50) if won_50_50 else None,
        attempts_50_50=len(won_50_50) if won_50_50 else None,
        expected_pity=sum(won_pitys) / len(won_pitys) if won_pitys else None,
    )
