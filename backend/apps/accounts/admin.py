"""Admin for accounts. The password is edited through Django's hash form."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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
