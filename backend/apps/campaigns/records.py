"""Import surface kept for callers that already use this module.

The match lives in `match`, invites in `invitations`, notices in `notices`,
and list reads in `queries`.
"""

from .access import _actor
from .errors import CampaignError, RevisionConflict
from .invitations import (
    accept_alias,
    accept_link,
    decline_invitation,
    invite_alias,
    invite_link,
    list_invitations,
    preview_link,
    resend_invitation,
    revoke_invitation,
    search_players,
)
from .match import (
    create_campaign,
    deactivate_account,
    play,
    present,
    present_fort_delta,
    present_roads_delta,
    read_campaign,
    scrap_campaign,
)
from .notices import list_notifications, mark_notification_read
from .queries import campaign_pulse, inbox, list_campaigns
from .store import _sync

__all__ = [
    "CampaignError",
    "RevisionConflict",
    "_actor",
    "_sync",
    "accept_alias",
    "accept_link",
    "campaign_pulse",
    "create_campaign",
    "deactivate_account",
    "decline_invitation",
    "inbox",
    "invite_alias",
    "invite_link",
    "list_campaigns",
    "list_invitations",
    "list_notifications",
    "mark_notification_read",
    "play",
    "present",
    "present_fort_delta",
    "present_roads_delta",
    "preview_link",
    "read_campaign",
    "resend_invitation",
    "revoke_invitation",
    "scrap_campaign",
    "search_players",
]
