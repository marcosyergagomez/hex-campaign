"""Admin for accounts. The password is edited through Django's hash form."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PlayerSession, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "alias", "email_verified_at", "is_active", "is_staff")
    search_fields = ("email", "alias")
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("email", "alias", "password")}),
        ("Perfil", {"fields": ("birth_date", "sex")}),
        ("Verificación", {"fields": ("email_verified_at", "created_at")}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "alias", "birth_date", "sex", "password1", "password2"),
            },
        ),
    )


@admin.register(PlayerSession)
class PlayerSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "last_seen_at", "expires_at")
    fields = ("user", "created_at", "last_seen_at", "expires_at")
    readonly_fields = ("user", "created_at", "last_seen_at", "expires_at")

    def has_add_permission(self, request) -> bool:
        return False
