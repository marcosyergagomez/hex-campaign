"""Admin view of the stored campaign state."""

from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
    search_fields = ("name",)
