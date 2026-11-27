"""Failures of the campaign application, translated by the HTTP layer."""


class CampaignError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RevisionConflict(CampaignError):
    def __init__(self) -> None:
        super().__init__("revision_conflict")


# Visible lifecycle: prepared (recruiting/placing/preparing), running, finished.
PREPARED_PHASES = ("recruiting", "placing", "preparing")
RUNNING_PHASES = ("orders", "battles")
RUNNING_CAMPAIGN_LIMIT = 3
