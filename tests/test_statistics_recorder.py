"""Recorder regression for imported pump statistics."""

from datetime import datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator

_BASE_TS = datetime(2026, 3, 1, 12, 0, 0)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_db_url, enable_custom_integrations):
    """Prepare the recorder database before Home Assistant is initialized."""
    yield


async def _make_coordinator(hass):
    return await make_tandem_coordinator(hass)


def _make_cgm_event(seq, glucose_mgdl):
    return {"event_id": 256, "seq": seq, "timestamp": _BASE_TS, "glucose_mgdl": glucose_mgdl}


async def test_imported_and_live_statistics_can_share_an_hour(recorder_mock, hass: HomeAssistant):
    """Pump imports and recorder-owned sensor statistics must not share an ID."""
    from datetime import timezone

    from homeassistant.components.recorder.models import StatisticMeanType
    from homeassistant.components.recorder.statistics import async_import_statistics, statistics_during_period
    from pytest_homeassistant_custom_component.components.recorder.common import async_recorder_block_till_done

    coordinator = await _make_coordinator(hass)
    start = _BASE_TS.replace(tzinfo=timezone.utc)
    live_id = "sensor.tandem_last_glucose_level_mmol"
    imported_id = "tandem:last_glucose_level_mmol"
    async_import_statistics(
        hass,
        {
            "statistic_id": live_id,
            "source": "recorder",
            "name": "Live glucose",
            "unit_of_measurement": "mmol/L",
            "unit_class": None,
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
        },
        [{"start": start, "mean": 8.0, "min": 8.0, "max": 8.0}],
    )
    assert await coordinator._import_statistics([_make_cgm_event(seq=1, glucose_mgdl=120)]) == []
    await async_recorder_block_till_done(hass)
    result = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        start - timedelta(days=2),
        start + timedelta(days=2),
        {live_id, imported_id},
        "hour",
        None,
        {"mean"},
    )
    assert len(result[live_id]) == 1
    assert len(result[imported_id]) == 1
    assert result[live_id][0]["mean"] == 8.0
    assert result[imported_id][0]["mean"] != 8.0

