"""Turn a saved map into the document, and the document back into a map."""

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex, disk
from hexcampaign.domain.land import checked_home_size
from hexcampaign.domain.maps import Template
from hexcampaign.domain.rules import MAP_SIZES
from hexcampaign.domain.terrain import Plot, checked_plot, passable


def dump_template(template: Template) -> dict[str, object]:
    cells = [
        {
            "q": cell.q,
            "r": cell.r,
            "ground": plot.ground,
            "road": plot.road,
            "bridge": plot.bridge,
        }
        for cell, plot in sorted(template.cells.items())
    ]
    return {
        "version": 1,
        "size": template.size,
        "seats": template.seats,
        "generated": template.generated,
        "home_size": template.home_size,
        "cells": cells,
        "anchors": [{"q": cell.q, "r": cell.r} for cell in template.anchors],
    }


def load_template(data: object) -> Template:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise DomainError("rules_invalid")
    try:
        size = data["size"]
        seats = data["seats"]
        generated = data["generated"]
        raw_cells = data["cells"]
        raw_anchors = data["anchors"]
    except KeyError as exc:
        raise DomainError("rules_invalid") from exc
    if size not in MAP_SIZES or not isinstance(generated, bool):
        raise DomainError("rules_invalid")
    if seats is not None and seats not in {2, 3, 4}:
        raise DomainError("rules_invalid")
    if not isinstance(raw_cells, list) or not isinstance(raw_anchors, list):
        raise DomainError("rules_invalid")
    if not raw_cells:
        raise DomainError("rules_invalid")
    plots: dict[Hex, Plot] = {}
    for item in raw_cells:
        cell, plot = _cell(item)
        if cell in plots:
            raise DomainError("rules_invalid")
        plots[cell] = plot
    board = set(disk(size))
    present = set(plots)
    if not present <= board:
        raise DomainError("rules_invalid")
    if generated and present != board:
        raise DomainError("rules_invalid")
    anchors = tuple(_anchor(item) for item in raw_anchors)
    if len(set(anchors)) != len(anchors):
        raise DomainError("rules_invalid")
    if anchors:
        if len(anchors) not in {2, 3, 4}:
            raise DomainError("rules_invalid")
        for cell in anchors:
            if cell not in plots or not passable(plots[cell]):
                raise DomainError("rules_invalid")
    seats = _seats(seats, anchors, generated)
    home_size = checked_home_size(data.get("home_size"), size)
    return Template(size, seats, generated, plots, anchors, home_size)


def drawn(
    size: int,
    cells: list[dict[str, object]],
    anchors: list[dict[str, object]] | None = None,
) -> Template:
    spots = anchors or []
    return load_template(
        {
            "version": 1,
            "size": size,
            "seats": len(spots) if spots else None,
            "generated": False,
            "cells": cells,
            "anchors": spots,
        }
    )


def _seats(seats: int | None, anchors: tuple[Hex, ...], generated: bool) -> int | None:
    expected = len(anchors) if anchors else None
    if generated:
        if seats is None or expected != seats:
            raise DomainError("rules_invalid")
        return seats
    if seats is None:
        return expected
    if seats != expected:
        raise DomainError("rules_invalid")
    return seats


def _cell(item: object) -> tuple[Hex, Plot]:
    if not isinstance(item, dict):
        raise DomainError("rules_invalid")
    try:
        cell = Hex(_coord(item["q"]), _coord(item["r"]))
        plot = checked_plot(item["ground"], item["road"] is True, item["bridge"] is True)
    except KeyError as exc:
        raise DomainError("rules_invalid") from exc
    return cell, plot


def _anchor(item: object) -> Hex:
    if not isinstance(item, dict):
        raise DomainError("rules_invalid")
    try:
        return Hex(_coord(item["q"]), _coord(item["r"]))
    except KeyError as exc:
        raise DomainError("rules_invalid") from exc


def _coord(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainError("rules_invalid")
    if value < -64 or value > 64:
        raise DomainError("rules_invalid")
    return value
