"""
Decoding of Solvis weekly schedules (Wochenplan).

A schedule is a block of 42 holding registers: 7 days, 3 start/stop pairs per day,
one register each. Every value is a quarter-hour index, 0 = 00:00 .. 95 = 23:45.
"""

import logging
from datetime import datetime, time, timedelta

from ..const import (
    SCHEDULE_DAY_KEYS,
    SCHEDULE_DAYS,
    SCHEDULE_MAX_INDEX,
    SCHEDULE_MINUTES_PER_STEP,
    SCHEDULE_REGISTER_COUNT,
    SCHEDULE_SLOTS_PER_DAY,
)

_LOGGER = logging.getLogger(__name__)


def index_to_time(index: int) -> time | None:
    """Convert a quarter-hour index (0..95) into a time, or None if out of range."""
    if not isinstance(index, int) or not 0 <= index <= SCHEDULE_MAX_INDEX:
        return None
    hour, minute = divmod(index * SCHEDULE_MINUTES_PER_STEP, 60)
    return time(hour=hour, minute=minute)


def decode_schedule(words) -> dict[str, list[tuple[time, time]]]:
    """
    Turn the 42 raw registers into {day_key: [(start, stop), ...]}.

    Slots where start == stop are unused and are dropped, as are slots holding a
    value outside 0..95. Days without any usable slot map to an empty list, so the
    result always has all seven keys.
    """
    schedule: dict[str, list[tuple[time, time]]] = {key: [] for key in SCHEDULE_DAY_KEYS}

    if words is None or len(words) < SCHEDULE_REGISTER_COUNT:
        _LOGGER.debug("Schedule block too short: got %s registers", 0 if words is None else len(words))
        return schedule

    for day in range(SCHEDULE_DAYS):
        for slot in range(SCHEDULE_SLOTS_PER_DAY):
            offset = day * SCHEDULE_SLOTS_PER_DAY * 2 + slot * 2
            start, stop = index_to_time(words[offset]), index_to_time(words[offset + 1])

            if start is None or stop is None:
                _LOGGER.debug("Skipping slot %s/%s with out-of-range values %s/%s", day, slot, words[offset], words[offset + 1])
                continue
            if start == stop:  # unused slot
                continue

            schedule[SCHEDULE_DAY_KEYS[day]].append((start, stop))

    return schedule


def schedule_as_attributes(schedule: dict[str, list[tuple[time, time]]]) -> dict[str, list[str]]:
    """Render a decoded schedule as JSON-friendly "HH:MM-HH:MM" strings per day."""
    return {day: [f"{start:%H:%M}-{stop:%H:%M}" for start, stop in slots] for day, slots in schedule.items()}


def _slots_for(schedule: dict[str, list[tuple[time, time]]], moment: datetime) -> list[tuple[time, time]]:
    return schedule.get(SCHEDULE_DAY_KEYS[moment.weekday()], [])


def is_active(schedule: dict[str, list[tuple[time, time]]], moment: datetime) -> bool:
    """Is `moment` inside one of that weekday's windows? Start inclusive, stop exclusive."""
    now = moment.time()
    return any(start <= now < stop for start, stop in _slots_for(schedule, moment))


def next_switch(schedule: dict[str, list[tuple[time, time]]], moment: datetime) -> datetime | None:
    """
    The next instant the schedule changes state, searching up to a week ahead.

    Returns None for an empty schedule, which has no switching points at all.
    """
    if not any(schedule.values()):
        return None

    for day_offset in range(SCHEDULE_DAYS + 1):
        day = moment + timedelta(days=day_offset)
        boundaries = sorted({edge for slot in _slots_for(schedule, day) for edge in slot})

        for boundary in boundaries:
            candidate = day.replace(hour=boundary.hour, minute=boundary.minute, second=0, microsecond=0)
            if candidate > moment:
                return candidate

    return None
