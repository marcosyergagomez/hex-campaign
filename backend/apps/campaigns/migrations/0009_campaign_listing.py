from django.db import migrations, models


def copy_listing_index(apps, _schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    from apps.campaigns.projection import index_from_state

    for row in Campaign.objects.all().iterator():
        found = index_from_state(row.state)
        row.turn = found.get("turn", 0)
        row.seat_limit = found.get("seat_limit", 0)
        row.occupied = found.get("occupied", 0)
        row.save(update_fields=["turn", "seat_limit", "occupied"])


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0008_campaign_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="turn",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="campaign",
            name="seat_limit",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="campaign",
            name="occupied",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(copy_listing_index, migrations.RunPython.noop),
    ]
