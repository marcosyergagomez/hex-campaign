"""Player heraldry; faction names do not alter the campaign rules."""

from hexcampaign.domain.errors import DomainError

FACTIONS = (
    "empire", "bretonnia", "dwarfs", "high_elves", "wood_elves", "cathay",
    "orcs_goblins", "warriors_chaos", "beastmen", "tomb_kings",
    "chaos_dwarfs", "daemons_chaos", "dark_elves", "lizardmen",
    "ogre_kingdoms", "skaven", "vampire_counts",
)
LEGACY = frozenset(FACTIONS[10:])
COLORS = {
    "garnet": "#ac454f",
    "azure": "#3974b5",
    "emerald": "#318267",
    "ochre": "#b38729",
    "violet": "#8356a6",
    "copper": "#bf683c",
    "teal": "#268d98",
    "rose": "#b65c88",
}


def checked_identity(faction: object, color: object, *, optional: bool = False) -> tuple[str, str]:
    if optional and faction == "" and color == "":
        return "", ""
    if not isinstance(faction, str) or faction not in FACTIONS:
        raise DomainError("faction_invalid")
    if not isinstance(color, str) or color not in COLORS.values():
        raise DomainError("color_invalid")
    return faction, color
