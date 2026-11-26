"""Player heraldry; faction names do not alter the campaign rules."""

from hexcampaign.domain.errors import DomainError

FACTIONS = (
    "empire", "bretonnia", "dwarfs", "high_elves", "wood_elves", "cathay",
    "orcs_goblins", "warriors_chaos", "beastmen", "tomb_kings",
    "chaos_dwarfs", "daemons_chaos", "dark_elves", "lizardmen",
    "ogre_kingdoms", "skaven", "vampire_counts",
)
LEGACY = frozenset(FACTIONS[10:])
# Sixteen hues spaced around the wheel so territory washes stay easy to tell apart.
COLORS = {
    "garnet": "#c62828",
    "copper": "#ef6c00",
    "ochre": "#f9a825",
    "lime": "#9ccc65",
    "emerald": "#2e7d32",
    "teal": "#00838f",
    "azure": "#1565c0",
    "sky": "#0288d1",
    "indigo": "#283593",
    "violet": "#6a1b9a",
    "rose": "#c2185b",
    "crimson": "#880e4f",
    "sand": "#a1887f",
    "olive": "#827717",
    "slate": "#455a64",
    "ivory": "#c0a062",
}
# Older washes already stored on seats remain valid.
_LEGACY_COLORS = frozenset(
    {
        "#ac454f",
        "#3974b5",
        "#318267",
        "#b38729",
        "#8356a6",
        "#bf683c",
        "#268d98",
        "#b65c88",
    }
)


def checked_color(color: object) -> str:
    if not isinstance(color, str) or (
        color not in COLORS.values() and color not in _LEGACY_COLORS
    ):
        raise DomainError("color_invalid")
    return color


def checked_identity(faction: object, color: object, *, optional: bool = False) -> tuple[str, str]:
    if not isinstance(faction, str) or (faction != "" and faction not in FACTIONS):
        raise DomainError("faction_invalid")
    if faction == "":
        if optional and color == "":
            return "", ""
        if optional:
            return "", checked_color(color)
        raise DomainError("faction_invalid")
    return faction, checked_color(color)
