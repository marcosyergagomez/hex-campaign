"""User identified by email.

This model has to exist before the first migration. Django builds the
permission tables against whatever AUTH_USER_MODEL is at that moment.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .validation import (
    SEX_MESSAGE,
    Sex,
    alias_errors,
    birth_date_errors,
    canonical_alias,
    canonical_email,
)


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields: object):
        if not email or not str(email).strip():
            raise ValueError("An email is required.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: object):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff and is_superuser set.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="correo")
    alias = models.CharField(
        max_length=24,
        verbose_name="alias",
        help_text="De 3 a 24 letras, números o guion bajo. No distingue mayúsculas.",
    )
    birth_date = models.DateField(verbose_name="fecha de nacimiento")
    sex = models.CharField(
        max_length=16,
        choices=Sex.choices,
        verbose_name="sexo",
        error_messages={"invalid_choice": SEX_MESSAGE},
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["alias", "birth_date", "sex"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(
                Lower("alias"),
                name="accounts_user_alias_ci",
                violation_error_code="alias_taken",
                violation_error_message="Ese alias ya está en uso.",
            ),
            models.CheckConstraint(
                condition=models.Q(sex__in=tuple(Sex.values)),
                name="accounts_user_sex_known",
            ),
            models.CheckConstraint(
                condition=models.Q(alias__regex=r"^[A-Za-z0-9_]{3,24}$"),
                name="accounts_user_alias_shape",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self._canonicalize()
        errors: dict[str, list[str]] = {}
        if self.alias:
            errors.update(alias_errors(self.alias))
        if self.birth_date:
            errors.update(birth_date_errors(self.birth_date, timezone.localdate()))
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self._canonicalize()
        self.full_clean()
        super().save(*args, **kwargs)

    def _canonicalize(self) -> None:
        if isinstance(self.email, str):
            self.email = canonical_email(self.email)
        if isinstance(self.alias, str):
            self.alias = canonical_alias(self.alias)

    def __str__(self) -> str:
        return self.alias or self.email


class EmailVerification(models.Model):
    """One confirmation secret. Only its SHA-256 digest is stored."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verifications",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "confirmación de correo"
        verbose_name_plural = "confirmaciones de correo"

    def __str__(self) -> str:
        return f"{self.user_id} {self.expires_at:%Y-%m-%d}"
