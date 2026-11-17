"""The campaign row keeps its state after a new read."""

import pytest

from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_campaign_state_is_stored_and_reloaded() -> None:
    campaign = Campaign.objects.create(
        name="Primera",
        state={"version": 1, "phase": "setup"},
    )

    campaign.state = {"version": 1, "phase": "playing"}
    campaign.save(update_fields=["state", "updated_at"])

    reloaded = Campaign.objects.get(pk=campaign.pk)
    assert reloaded.state == {"version": 1, "phase": "playing"}
    assert reloaded.updated_at >= reloaded.created_at
