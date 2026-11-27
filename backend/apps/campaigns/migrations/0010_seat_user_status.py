from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0009_campaign_listing"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="seat",
            index=models.Index(fields=["user", "status"], name="seat_user_status"),
        ),
    ]
