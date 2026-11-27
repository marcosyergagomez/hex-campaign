"""Print the domain movement table so the browser test can compare it."""

import json

from hexcampaign.domain.terrain import (
    EXPLORER_GAZE_BONUS,
    EXPLORER_MOVE_BONUS,
    GROUNDS,
    IMPASSABLE,
    Plot,
    exit_cost,
    gaze_from,
    passable,
    road_refund,
)
from hexcampaign.domain.units import move_budget, unit_gaze


class Army:
    def __init__(self, kind: str) -> None:
        self.kind = kind


rows = []
for ground in sorted(GROUNDS):
    plot = Plot(ground)
    row = {
        "ground": ground,
        "passable": passable(plot),
        "gaze": gaze_from(plot),
        "refund": road_refund(plot),
    }
    if passable(plot):
        row["exit"] = exit_cost(plot)
        row["road"] = exit_cost(Plot(ground, road=True))
        row["road_refund"] = road_refund(Plot(ground, road=True))
        if ground == "rio":
            row["bridge"] = exit_cost(Plot(ground, bridge=True))
    rows.append(row)

print(json.dumps({
    "rows": rows,
    "impassable": sorted(IMPASSABLE),
    "unknown_gaze": gaze_from(None),
    "explorer_move_bonus": EXPLORER_MOVE_BONUS,
    "explorer_gaze_bonus": EXPLORER_GAZE_BONUS,
    "army_budget": move_budget(3, Army("army")),
    "explorer_budget": move_budget(3, Army("explorer")),
    "explorer_gaze_hill": unit_gaze(Army("explorer"), Plot("colina")),
    "army_gaze_plain": unit_gaze(Army("army"), Plot("llanura")),
}))
