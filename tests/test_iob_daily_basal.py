"""Regression tests for pump-recorded IOB and its source timestamp."""

from datetime import datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator
from custom_components.tandem.const import TANDEM_SENSOR_KEY_ACTIVE_INSULIN, TANDEM_SENSOR_KEY_IOB_TIMESTAMP, UNAVAILABLE
from custom_components.tandem.tandem_api import map_pump_log_event


def test_source_maps_daily_basal_iob():
    """The BFF daily basal record retains the pump IOB without unit conversion."""
    event = map_pump_log_event({
        "eventCode": 81, "pumpDateTime": "2026-11-10T09:00:00", "sequenceNumber": 42,
        "eventProperties": {"iob": 2.325, "dailyTotalBasal": 4.0, "lastBasalRate": 0.8},
    })
    assert event is not None
    assert event["iob"] == 2.325
    assert event["seq"] == 42


async def test_daily_iob_overrides_bolus_and_records_breadcrumbs(hass: HomeAssistant):
    """Use newest daily IOB even when bolus records exist, including zero values."""
    coordinator = await make_tandem_coordinator(hass)
    now = datetime(2026, 11, 10, 9, 0)
    events = [
        {"event_id": 81, "timestamp": now - timedelta(minutes=10), "iob": 3.4, "seq": 11},
        {"event_id": 20, "timestamp": now, "iob": 5.0, "seq": 12, "insulin_delivered": 1.0},
        {"event_id": 81, "timestamp": now + timedelta(minutes=10), "iob": 0.0, "seq": 13},
    ]
    data = {}
    coordinator._parse_pump_events(events, data)
    assert data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] == 0.0
    attrs = data[f"{TANDEM_SENSOR_KEY_ACTIVE_INSULIN}_attributes"]
    assert attrs["source"] == "daily_basal"
    assert attrs["source_event_code"] == 81
    assert attrs["source_sequence"] == 13
    assert attrs["source_timestamp"] == data[TANDEM_SENSOR_KEY_IOB_TIMESTAMP]
    assert [v["v"] for v in attrs["readings"]] == [3.4, 0.0]


@pytest.mark.parametrize("invalid", [None, float("nan"), -1, True, "2.0"])
async def test_invalid_latest_daily_iob_does_not_fall_back(hass: HomeAssistant, invalid):
    """Never replace a malformed latest value with an older, misleading IOB."""
    coordinator = await make_tandem_coordinator(hass)
    now = datetime(2026, 11, 10, 9, 0)
    data = {}
    coordinator._parse_pump_events([
        {"event_id": 81, "timestamp": now, "iob": 3.0, "seq": 1},
        {"event_id": 81, "timestamp": now + timedelta(minutes=10), "iob": invalid, "seq": 2},
    ], data)
    assert data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] is UNAVAILABLE
