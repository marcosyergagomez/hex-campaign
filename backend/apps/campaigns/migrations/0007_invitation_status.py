from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0006_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="declined_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invitation",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
