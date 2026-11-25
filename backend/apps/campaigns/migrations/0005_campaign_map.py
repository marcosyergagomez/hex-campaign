from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_player_session"),
        ("campaigns", "0004_campaign_created_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignMap",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("size", models.PositiveSmallIntegerField()),
                ("seats", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("generated", models.BooleanField(default=False)),
                ("document", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="campaign_maps",
                        to="accounts.user",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="campaignmap",
            index=models.Index(fields=["owner", "created_at"], name="campaign_map_owner"),
        ),
    ]
