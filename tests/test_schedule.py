"""Tests for decoding Solvis weekly schedules."""

from datetime import datetime, time

import pytest

from custom_components.solvis_control.utils.schedule import (
    decode_schedule,
    index_to_time,
    is_active,
    next_switch,
    schedule_as_attributes,
)

MONDAY = datetime(2026, 8, 17)  # a Monday
SUNDAY = datetime(2026, 8, 23)


def build(**days):
    """Build a 42-register block. days: monday=[(start_idx, stop_idx), ...]."""
    order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    words = [0] * 42
    for day_name, slots in days.items():
        day = order.index(day_name)
        for slot, (start, stop) in enumerate(slots):
            offset = day * 6 + slot * 2
            words[offset], words[offset + 1] = start, stop
    return words


@pytest.mark.parametrize(
    "index, expected",
    [
        (0, time(0, 0)),
        (1, time(0, 15)),
        (24, time(6, 0)),
        (95, time(23, 45)),  # last valid index
        (96, None),  # one past midnight
        (-1, None),
        (65535, None),  # unwritten register
        ("x", None),
    ],
)
def test_index_to_time(index, expected):
    assert index_to_time(index) == expected


def test_decode_schedule_reads_all_days_and_slots():
    words = build(monday=[(24, 32), (64, 88)], sunday=[(0, 4)])
    schedule = decode_schedule(words)

    assert schedule["monday"] == [(time(6, 0), time(8, 0)), (time(16, 0), time(22, 0))]
    assert schedule["sunday"] == [(time(0, 0), time(1, 0))]
    assert schedule["wednesday"] == []
    assert set(schedule) == {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


def test_unused_slots_are_dropped():
    """start == stop marks an unused slot and must not become a zero-length window."""
    schedule = decode_schedule(build(monday=[(0, 0), (24, 32), (50, 50)]))
    assert schedule["monday"] == [(time(6, 0), time(8, 0))]


def test_out_of_range_values_are_ignored():
    schedule = decode_schedule(build(monday=[(24, 32), (65535, 65535), (200, 300)]))
    assert schedule["monday"] == [(time(6, 0), time(8, 0))]


def test_short_or_missing_block_yields_empty_week():
    for words in (None, [], [0] * 41):
        schedule = decode_schedule(words)
        assert all(slots == [] for slots in schedule.values())
        assert len(schedule) == 7


def test_schedule_as_attributes_is_json_friendly():
    attrs = schedule_as_attributes(decode_schedule(build(monday=[(24, 32)])))
    assert attrs["monday"] == ["06:00-08:00"]
    assert attrs["tuesday"] == []


@pytest.mark.parametrize(
    "hour, minute, expected",
    [
        (5, 59, False),
        (6, 0, True),  # start is inclusive
        (7, 0, True),
        (7, 59, True),
        (8, 0, False),  # stop is exclusive
        (16, 30, True),  # second window
    ],
)
def test_is_active_window_boundaries(hour, minute, expected):
    schedule = decode_schedule(build(monday=[(24, 32), (64, 88)]))
    assert is_active(schedule, MONDAY.replace(hour=hour, minute=minute)) is expected


def test_is_active_only_considers_the_right_weekday():
    schedule = decode_schedule(build(monday=[(24, 32)]))
    assert is_active(schedule, MONDAY.replace(hour=7)) is True
    assert is_active(schedule, MONDAY.replace(day=18, hour=7)) is False  # Tuesday


def test_next_switch_walks_forward_through_the_day():
    schedule = decode_schedule(build(monday=[(24, 32), (64, 88)]))

    assert next_switch(schedule, MONDAY.replace(hour=5)) == MONDAY.replace(hour=6)
    assert next_switch(schedule, MONDAY.replace(hour=7)) == MONDAY.replace(hour=8)
    assert next_switch(schedule, MONDAY.replace(hour=9)) == MONDAY.replace(hour=16)


def test_next_switch_wraps_into_the_following_week():
    """From Sunday evening the next switch is Monday's first start."""
    schedule = decode_schedule(build(monday=[(24, 32)]))
    assert next_switch(schedule, SUNDAY.replace(hour=23)) == datetime(2026, 8, 24, 6, 0)


def test_next_switch_returns_none_for_an_empty_schedule():
    assert next_switch(decode_schedule([0] * 42), MONDAY) is None


def test_next_switch_is_strictly_in_the_future():
    """Standing exactly on a boundary must return the following one, not the same instant."""
    schedule = decode_schedule(build(monday=[(24, 32)]))
    assert next_switch(schedule, MONDAY.replace(hour=6)) == MONDAY.replace(hour=8)


# # # Entities # # #


def _entity_deps():
    from unittest.mock import MagicMock
    from homeassistant.helpers.entity import DeviceInfo

    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.data = {}
    coordinator.last_update_success = True
    coordinator.is_register_available.return_value = True
    return coordinator, DeviceInfo(identifiers={("solvis", "dummy")})


def test_schedule_sensor_exposes_week_and_next_switch(monkeypatch):
    from unittest.mock import MagicMock
    from custom_components.solvis_control.sensor import SolvisScheduleSensor
    from custom_components.solvis_control import sensor as sensor_module

    coordinator, device_info = _entity_deps()
    coordinator.data = {"hkr1_schedule": tuple(build(monday=[(24, 32)]))}

    entity = SolvisScheduleSensor(coordinator=coordinator, device_info=device_info, host="h", name="hkr1_schedule", modbus_address=34048)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    monkeypatch.setattr(sensor_module.dt_util, "now", lambda: MONDAY.replace(hour=5))
    entity._async_update_from_coordinator()

    assert entity._attr_native_value == MONDAY.replace(hour=6)
    assert entity._attr_extra_state_attributes["monday"] == ["06:00-08:00"]
    entity.async_write_ha_state.assert_called_once()


def test_schedule_sensor_without_data_stays_empty():
    from unittest.mock import MagicMock
    from custom_components.solvis_control.sensor import SolvisScheduleSensor

    coordinator, device_info = _entity_deps()
    entity = SolvisScheduleSensor(coordinator=coordinator, device_info=device_info, host="h", name="hkr1_schedule", modbus_address=34048)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    entity._async_update_from_coordinator()

    assert entity._attr_native_value is None
    assert entity._attr_extra_state_attributes == {}

    coordinator.is_register_available.return_value = False
    assert not entity.available


def test_schedule_binary_sensor_arms_a_timer_at_the_next_boundary(monkeypatch):
    """The state must flip on the slot edge, not whenever the next poll happens."""
    from unittest.mock import MagicMock
    from custom_components.solvis_control.binary_sensor import SolvisScheduleBinarySensor
    from custom_components.solvis_control import binary_sensor as bs_module

    coordinator, device_info = _entity_deps()
    coordinator.data = {"hkr1_schedule": tuple(build(monday=[(24, 32)]))}

    scheduled = []
    monkeypatch.setattr(bs_module, "async_track_point_in_time", lambda hass, cb, when: scheduled.append(when) or MagicMock())
    monkeypatch.setattr(bs_module.dt_util, "now", lambda: MONDAY.replace(hour=7))

    entity = SolvisScheduleBinarySensor(coordinator=coordinator, device_info=device_info, host="h", name="hkr1_schedule_active", source_key="hkr1_schedule", modbus_address=34048)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    entity._async_refresh()

    assert entity._attr_is_on is True
    assert scheduled == [MONDAY.replace(hour=8)]  # armed for the end of the window


def test_schedule_binary_sensor_cancels_the_previous_timer(monkeypatch):
    from unittest.mock import MagicMock
    from custom_components.solvis_control.binary_sensor import SolvisScheduleBinarySensor
    from custom_components.solvis_control import binary_sensor as bs_module

    coordinator, device_info = _entity_deps()
    coordinator.data = {"hkr1_schedule": tuple(build(monday=[(24, 32)]))}

    unsub = MagicMock()
    monkeypatch.setattr(bs_module, "async_track_point_in_time", lambda hass, cb, when: unsub)
    monkeypatch.setattr(bs_module.dt_util, "now", lambda: MONDAY.replace(hour=7))

    entity = SolvisScheduleBinarySensor(coordinator=coordinator, device_info=device_info, host="h", name="hkr1_schedule_active", source_key="hkr1_schedule", modbus_address=34048)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    entity._async_refresh()
    entity._async_refresh()  # a second update must not leak the first timer

    unsub.assert_called_once()


def test_schedule_binary_sensor_without_data_is_unknown():
    from unittest.mock import MagicMock
    from custom_components.solvis_control.binary_sensor import SolvisScheduleBinarySensor

    coordinator, device_info = _entity_deps()
    entity = SolvisScheduleBinarySensor(coordinator=coordinator, device_info=device_info, host="h", name="hkr1_schedule_active", source_key="hkr1_schedule", modbus_address=34048)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    entity._async_refresh()

    assert entity._attr_is_on is None
