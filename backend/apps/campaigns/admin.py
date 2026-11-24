"""Admin view of the stored campaign state."""

from django.contrib import admin

from .models import Campaign, Invitation, Seat


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "phase", "created_by", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("alias", "role", "status", "campaign")
    search_fields = ("alias",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("campaign", "invited_user", "created_at", "accepted_at")
    readonly_fields = ("token_hash", "created_at")
