"""The process counters log the three operational events."""

import logging

from apps.campaigns.telemetry import (
    note_revision_conflict,
    note_turn_resolved,
    note_unhandled,
    reset,
    snapshot,
)


def setup_function() -> None:
    reset()


def test_a_resolved_turn_and_a_conflict_increment_separate_counters(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="hexcampaign.campaigns"):
        note_turn_resolved()
        note_revision_conflict()
        note_turn_resolved()
    assert snapshot()["turn_resolved"] == 2
    assert snapshot()["revision_conflict"] == 1
    assert "event=turn_resolved count=2 request_id=-" in caplog.text
    assert "event=revision_conflict count=1 request_id=-" in caplog.text


def test_an_unhandled_error_logs_the_given_request_id(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="hexcampaign.campaigns"):
        note_unhandled("trace-500")
    assert snapshot()["unhandled"] == 1
    assert "event=unhandled count=1 request_id=trace-500" in caplog.text
