"""The match lives in the campaign document. Seat rows are only an index."""

import uuid

from django.conf import settings
from django.db import models


def initial_campaign_state() -> dict[str, object]:
    return {"version": 1, "phase": "setup"}


class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    # Copied from the document so a player's list does not load every order.
    phase = models.CharField(max_length=16, default="setup")
    state = models.JSONField(default=initial_campaign_state)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="campaigns_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["created_by", "phase"], name="campaign_creator_phase"),
        ]

    def save(self, *args, **kwargs):
        phase = self.state.get("phase") if isinstance(self.state, dict) else None
        if isinstance(phase, str) and phase:
            self.phase = phase[:16]
            fields = kwargs.get("update_fields")
            if fields is not None and "phase" not in fields:
                kwargs["update_fields"] = {*fields, "phase"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Seat(models.Model):
    """One player in one campaign, so a user's games are not a scan of every document."""

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="seats")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campaign_seats",
    )
    alias = models.CharField(max_length=24)
    role = models.CharField(max_length=16)
    status = models.CharField(max_length=16)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["campaign", "user"], name="uniq_campaign_seat"),
            models.CheckConstraint(
                condition=models.Q(role__in=["owner", "admin", "player"]),
                name="campaign_seat_role",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "inactive", "eliminated", "expelled"]),
                name="campaign_seat_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.alias} {self.role}"


class Invitation(models.Model):
    """An invite link or an alias notice. Only the digest of a link is stored."""

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="campaign_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.campaign_id} {self.created_at:%Y-%m-%d}"


class Notification(models.Model):
    """In-app notice for a player. Starts with campaign invites; more kinds follow."""

    KIND_CAMPAIGN_INVITE = "campaign_invite"
    KIND_CAMPAIGN_ADMIN = "campaign_admin"
    KIND_CAMPAIGN_BATTLE = "campaign_battle"
    KIND_TURN = "turn"
    KIND_BATTLE = "battle"
    KINDS = (KIND_CAMPAIGN_INVITE, KIND_CAMPAIGN_ADMIN, KIND_CAMPAIGN_BATTLE, KIND_TURN, KIND_BATTLE)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=32)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "read_at", "-created_at"], name="notif_user_unread"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.user_id}"


class CampaignMap(models.Model):
    """A reusable picture of the ground. A started campaign keeps its own copy."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campaign_maps",
    )
    name = models.CharField(max_length=120)
    size = models.PositiveSmallIntegerField()
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    generated = models.BooleanField(default=False)
    document = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["owner", "created_at"], name="campaign_map_owner"),
        ]

    def __str__(self) -> str:
        return self.name
