"""Living campaign state.

The JSON document is the state of one campaign. Later rules update this
row; they do not invent a second store.
"""

import uuid

from django.db import models


def initial_campaign_state() -> dict[str, object]:
    return {"version": 1, "phase": "setup"}


class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    state = models.JSONField(default=initial_campaign_state)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return self.name
