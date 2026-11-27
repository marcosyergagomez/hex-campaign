from django.db import migrations, models


def copy_revision(apps, schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    for row in Campaign.objects.all().iterator():
        state = row.state if isinstance(row.state, dict) else {}
        revision = state.get("revision") if isinstance(state, dict) else None
        if isinstance(revision, int) and revision >= 1 and revision != row.revision:
            row.revision = revision
            row.save(update_fields=["revision"])


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0007_invitation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(copy_revision, migrations.RunPython.noop),
    ]
