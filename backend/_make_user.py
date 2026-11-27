from datetime import date

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
email = "jugador@example.com"
alias = "JugadorMesa"
user = User.objects.filter(email=email).first()
if user is None:
    user = User.objects.create_user(
        email,
        "clave-segura-12",
        alias=alias,
        birth_date=date(1990, 1, 1),
        sex="undisclosed",
    )
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    print("created")
else:
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    print("exists")
print(user.email, user.alias)
