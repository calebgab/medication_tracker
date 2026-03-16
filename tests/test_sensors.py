"""Tests for sensor and binary_sensor entities."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.medication_tracker.sensor import (
    MedicationLastTakenSensor,
    MedicationNextDoseSensor,
    MedicationStreakSensor,
    MedicationTakenTodaySensor,
)
from custom_components.medication_tracker.binary_sensor import (
    MedicationDueSoonSensor,
    MedicationOverdueSensor,
)
from custom_components.medication_tracker.const import DOMAIN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(med_state: dict, med_config: dict | None = None):
    """Build a minimal mock coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.get_med_state = MagicMock(return_value=med_state)
    coordinator.get_medication = MagicMock(return_value=med_config or {"id": "x", "name": "TestMed"})
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


# ---------------------------------------------------------------------------
# Next dose sensor
# ---------------------------------------------------------------------------


class TestNextDoseSensor:
    def _make_sensor(self, state_data):
        coordinator = _make_coordinator(state_data)
        sensor = MedicationNextDoseSensor(coordinator, "entry1", "med1")
        return sensor

    def test_native_value_parses_datetime(self):
        now = datetime.now(tz=timezone.utc)
        sensor = self._make_sensor({"next_dose": now.isoformat(), "next_dose_time": "08:00"})
        result = sensor.native_value
        assert isinstance(result, datetime)

    def test_native_value_none_when_no_next_dose(self):
        sensor = self._make_sensor({"next_dose": None})
        assert sensor.native_value is None

    def test_name_includes_med_name(self):
        sensor = self._make_sensor({})
        assert "TestMed" in sensor.name

    def test_extra_state_attributes_includes_times(self):
        sensor = self._make_sensor({"times": ["08:00", "20:00"], "dose": "10mg", "notes": "", "next_dose_time": "08:00"})
        attrs = sensor.extra_state_attributes
        assert attrs["times"] == ["08:00", "20:00"]

    def test_unique_id_format(self):
        sensor = self._make_sensor({})
        assert "entry1" in sensor.unique_id
        assert "med1" in sensor.unique_id

    def test_available_false_when_coordinator_failed(self):
        coordinator = _make_coordinator({})
        coordinator.last_update_success = False
        sensor = MedicationNextDoseSensor(coordinator, "entry1", "med1")
        assert sensor.available is False

    def test_available_false_when_med_not_found(self):
        coordinator = _make_coordinator({})
        coordinator.get_medication = MagicMock(return_value=None)
        sensor = MedicationNextDoseSensor(coordinator, "entry1", "med1")
        assert sensor.available is False


# ---------------------------------------------------------------------------
# Last taken sensor
# ---------------------------------------------------------------------------


class TestLastTakenSensor:
    def _make_sensor(self, state_data):
        coordinator = _make_coordinator(state_data)
        return MedicationLastTakenSensor(coordinator, "entry1", "med1")

    def test_native_value_parses_datetime(self):
        now = datetime.now(tz=timezone.utc)
        sensor = self._make_sensor({"last_taken": now.isoformat()})
        result = sensor.native_value
        assert isinstance(result, datetime)

    def test_native_value_none_when_never_taken(self):
        sensor = self._make_sensor({"last_taken": None})
        assert sensor.native_value is None

    def test_extra_attrs_include_counts(self):
        sensor = self._make_sensor({"taken_today": 2, "skipped_today": 1, "dose": "100mg", "last_taken": None})
        attrs = sensor.extra_state_attributes
        assert attrs["taken_today"] == 2
        assert attrs["skipped_today"] == 1


# ---------------------------------------------------------------------------
# Streak sensor
# ---------------------------------------------------------------------------


class TestStreakSensor:
    def _make_sensor(self, streak: int):
        coordinator = _make_coordinator({"streak": streak})
        return MedicationStreakSensor(coordinator, "entry1", "med1")

    def test_native_value_returns_streak(self):
        sensor = self._make_sensor(7)
        assert sensor.native_value == 7

    def test_native_value_zero_when_no_streak(self):
        sensor = self._make_sensor(0)
        assert sensor.native_value == 0

    def test_icon_fire_for_week_streak(self):
        sensor = self._make_sensor(7)
        assert sensor.icon == "mdi:fire"

    def test_icon_fire_circle_for_month_streak(self):
        sensor = self._make_sensor(30)
        assert sensor.icon == "mdi:fire-circle"

    def test_icon_pill_for_low_streak(self):
        sensor = self._make_sensor(3)
        assert sensor.icon == "mdi:pill"

    def test_unit_is_days(self):
        sensor = self._make_sensor(0)
        assert sensor.native_unit_of_measurement == "days"


# ---------------------------------------------------------------------------
# Taken today sensor
# ---------------------------------------------------------------------------


class TestTakenTodaySensor:
    def _make_sensor(self, state_data):
        coordinator = _make_coordinator(state_data)
        return MedicationTakenTodaySensor(coordinator, "entry1", "med1")

    def test_native_value(self):
        sensor = self._make_sensor({"taken_today": 2})
        assert sensor.native_value == 2

    def test_native_value_defaults_zero(self):
        sensor = self._make_sensor({})
        assert sensor.native_value == 0

    def test_extra_attrs_include_scheduled_count(self):
        sensor = self._make_sensor(
            {"taken_today": 1, "doses_scheduled_today": 2, "skipped_today": 0, "scheduled_today": True}
        )
        attrs = sensor.extra_state_attributes
        assert attrs["doses_scheduled_today"] == 2


# ---------------------------------------------------------------------------
# Overdue binary sensor
# ---------------------------------------------------------------------------


class TestOverdueSensor:
    def _make_sensor(self, is_overdue: bool, overdue_since=None):
        state_data = {
            "is_overdue": is_overdue,
            "overdue_since": overdue_since,
            "dose": "100mg",
            "times": ["08:00"],
            "notes": "",
        }
        coordinator = _make_coordinator(state_data)
        return MedicationOverdueSensor(coordinator, "entry1", "med1")

    def test_is_on_when_overdue(self):
        sensor = self._make_sensor(True, "2024-01-01T08:00:00")
        assert sensor.is_on is True

    def test_is_off_when_not_overdue(self):
        sensor = self._make_sensor(False)
        assert sensor.is_on is False

    def test_icon_pill_off_when_overdue(self):
        sensor = self._make_sensor(True)
        assert sensor.icon == "mdi:pill-off"

    def test_icon_pill_when_not_overdue(self):
        sensor = self._make_sensor(False)
        assert sensor.icon == "mdi:pill"

    def test_extra_attrs_include_overdue_since(self):
        sensor = self._make_sensor(True, "2024-01-01T08:00:00")
        attrs = sensor.extra_state_attributes
        assert attrs["overdue_since"] == "2024-01-01T08:00:00"

    def test_unique_id_format(self):
        sensor = self._make_sensor(False)
        assert "entry1" in sensor.unique_id
        assert "med1" in sensor.unique_id


# ---------------------------------------------------------------------------
# Due soon binary sensor
# ---------------------------------------------------------------------------


class TestDueSoonSensor:
    def _make_sensor(self, is_due_soon: bool, next_dose: str | None = None):
        state_data = {
            "is_due_soon": is_due_soon,
            "next_dose": next_dose,
            "next_dose_time": "08:00",
            "dose": "100mg",
        }
        coordinator = _make_coordinator(state_data)
        return MedicationDueSoonSensor(coordinator, "entry1", "med1")

    def test_is_on_when_due_soon(self):
        sensor = self._make_sensor(True)
        assert sensor.is_on is True

    def test_is_off_when_not_due_soon(self):
        sensor = self._make_sensor(False)
        assert sensor.is_on is False

    def test_icon_bell_ring_when_due(self):
        sensor = self._make_sensor(True)
        assert sensor.icon == "mdi:bell-ring"

    def test_icon_bell_outline_when_not_due(self):
        sensor = self._make_sensor(False)
        assert sensor.icon == "mdi:bell-outline"
