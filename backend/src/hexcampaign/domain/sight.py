"""A player sees their own armies. Everyone else depends on the fog and the visibility rule."""

from hexcampaign.domain.game import Army, Game, living
from hexcampaign.domain.hexes import Hex, distance


def sees_army(game: Game, viewer: str, army: Army) -> bool:
    if army.player_id == viewer:
        return True
    if army.destroyed or army.q is None or army.r is None:
        return False
    if game.rules.visibility == "full":
        return True
    cell = Hex(army.q, army.r)
    if cell not in game.discovered.get(viewer, set()):
        return False
    if game.rules.visibility == "anonymous":
        return True
    return any(distance(cell, Hex(own.q, own.r)) <= 1 for own in living(game, viewer))


def known_hex(game: Game, viewer: str, cell: Hex) -> bool:
    if game.rules.visibility == "full":
        return cell in set(game.hexes)
    return cell in game.discovered.get(viewer, set())
