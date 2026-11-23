"""User identified by email.

This model has to exist before the first migration. Django builds the
permission tables against whatever AUTH_USER_MODEL is at that moment.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .validation import ALIAS_PATTERN, MINIMUM_AGE_YEARS, SEX_VALUES, age_on


class Sex(models.TextChoices):
    WOMAN = "woman", "Mujer"
    MAN = "man", "Hombre"
    OTHER = "other", "Otro"
    UNDISCLOSED = "undisclosed", "Prefiero no decirlo"


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields: object):
        if not email:
            raise ValueError("An email is required.")
        email = email.strip().lower()
        alias = extra_fields.get("alias")
        if isinstance(alias, str):
            extra_fields["alias"] = alias.strip()
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
        error_messages={
            "invalid_choice": "Elige woman, man, other o undisclosed.",
        },
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
                condition=models.Q(sex__in=SEX_VALUES),
                name="accounts_user_sex_known",
            ),
            models.CheckConstraint(
                condition=models.Q(alias__regex=r"^[A-Za-z0-9_]{3,24}$"),
                name="accounts_user_alias_shape",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if isinstance(self.email, str):
            self.email = self.email.strip().lower()
        if isinstance(self.alias, str):
            self.alias = self.alias.strip()
        errors: dict[str, list[str]] = {}
        if self.alias and not ALIAS_PATTERN.fullmatch(self.alias):
            errors["alias"] = ["El alias usa de 3 a 24 letras, números o guion bajo."]
        if self.birth_date and age_on(self.birth_date, timezone.localdate()) < MINIMUM_AGE_YEARS:
            errors["birth_date"] = ["Hay que tener al menos 16 años."]
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if isinstance(self.email, str):
            self.email = self.email.strip().lower()
        if isinstance(self.alias, str):
            self.alias = self.alias.strip()
        self.full_clean()
        return super().save(*args, **kwargs)

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
