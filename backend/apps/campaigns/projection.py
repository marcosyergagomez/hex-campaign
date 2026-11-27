"""Columns copied out of the campaign document.

Lists, the pulse and invitation previews read these fields. They do not parse
`state`. A new list field is added here and filled in `Campaign.save` in the
same write as the document.
"""

_TURN_MAX = 2_147_483_647
_SMALL_MAX = 32_767


def index_from_state(state: object) -> dict[str, object]:
    """Return the listing columns present in a stored document."""
    if not isinstance(state, dict):
        return {}
    found: dict[str, object] = {}
    phase = state.get("phase")
    if isinstance(phase, str) and phase:
        found["phase"] = phase[:16]
    revision = state.get("revision")
    if isinstance(revision, int) and revision >= 1:
        found["revision"] = revision
    turn = state.get("turn")
    if isinstance(turn, int) and not isinstance(turn, bool) and 0 <= turn <= _TURN_MAX:
        found["turn"] = turn
    rules = state.get("rules")
    if isinstance(rules, dict):
        seats = rules.get("seats")
        if isinstance(seats, int) and not isinstance(seats, bool) and 0 <= seats <= _SMALL_MAX:
            found["seat_limit"] = seats
    members = state.get("members")
    if isinstance(members, list):
        found["occupied"] = _occupied(members)
    return found


def _occupied(members: list[object]) -> int:
    count = 0
    for member in members:
        if isinstance(member, dict) and member.get("status") != "expelled":
            count += 1
    return min(count, _SMALL_MAX)
