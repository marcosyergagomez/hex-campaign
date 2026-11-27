"""The exit table is shared with the browser. These checks lock the domain to that file."""

import json
from pathlib import Path

from hexcampaign.domain.terrain import (
    EXPLORER_GAZE_BONUS,
    EXPLORER_MOVE_BONUS,
    GROUNDS,
    IMPASSABLE,
    OPEN_GROUNDS,
    Plot,
    exit_cost,
    gaze_from,
    passable,
    road_refund,
)
from hexcampaign.domain.units import move_budget


class _Kind:
    def __init__(self, kind: str) -> None:
        self.kind = kind


def _contract() -> dict:
    here = Path(__file__).resolve()
    for parent in here.parents:
        path = parent / "shared" / "terrain.json"
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
    raise AssertionError("shared/terrain.json is missing")


def test_domain_exit_costs_match_the_shared_table() -> None:
    contract = _contract()
    assert set(contract["grounds"]) == set(GROUNDS)
    assert set(contract["impassable"]) == set(IMPASSABLE)
    assert set(contract["open_grounds"]) == set(OPEN_GROUNDS)
    assert contract["explorer_move_bonus"] == EXPLORER_MOVE_BONUS
    assert contract["explorer_gaze_bonus"] == EXPLORER_GAZE_BONUS
    assert gaze_from(None) == contract["base_gaze"]
    for ground, cost in contract["exit"].items():
        plot = Plot(ground)
        assert passable(plot)
        assert exit_cost(plot) == cost
        assert exit_cost(Plot(ground, road=True)) == 1
        assert road_refund(plot) == 0
        rough = 0 if ground in OPEN_GROUNDS else 1
        assert road_refund(Plot(ground, road=True)) == rough
        assert gaze_from(plot) == contract["gaze"].get(ground, contract["base_gaze"])
    assert exit_cost(Plot("rio", bridge=True)) == 1
    for ground in IMPASSABLE:
        assert not passable(Plot(ground))
        assert gaze_from(Plot(ground)) == contract["gaze"].get(ground, contract["base_gaze"])


def test_explorer_budget_uses_the_shared_bonus() -> None:
    assert move_budget(3, _Kind("army")) == 3
    assert move_budget(3, _Kind("explorer")) == 3 + EXPLORER_MOVE_BONUS
