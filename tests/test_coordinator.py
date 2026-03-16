"""Tests for MedicationCoordinator."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.medication_tracker.coordinator import MedicationCoordinator
from custom_components.medication_tracker.const import OVERDUE_GRACE_MINUTES

from .conftest import make_aware_dt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_dt(hour: int, minute: int) -> datetime:
    today = date.today()
    return datetime(today.year, today.month, today.day, hour, minute, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestCoordinatorInit:
    async def test_empty_on_fresh_load(self, coordinator):
        assert coordinator.medications == []

    async def test_loads_from_storage(self, mock_hass):
        stored_data = {
            "medications": [
                {
                    "id": "abc",
                    "name": "TestMed",
                    "dose": "5mg",
                    "times": ["08:00"],
                    "days": [],
                    "notes": "",
                }
            ],
            "dose_log": {},
        }
        with patch(
            "custom_components.medication_tracker.coordinator.Store"
        ) as mock_store_cls:
            mock_store = AsyncMock()
            mock_store.async_load = AsyncMock(return_value=stored_data)
            mock_store.async_save = AsyncMock()
            mock_store_cls.return_value = mock_store

            coord = MedicationCoordinator(mock_hass, "entry_id")
            coord._store = mock_store
            await coord.async_load()

        assert len(coord.medications) == 1
        assert coord.medications[0]["name"] == "TestMed"

    async def test_old_dose_log_entries_pruned_on_load(self, mock_hass):
        """Dose log entries from previous days should be dropped on load."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        stored_data = {
            "medications": [
                {"id": "abc", "name": "X", "dose": "", "times": [], "days": [], "notes": ""}
            ],
            "dose_log": {
                "abc": [{"date": yesterday, "taken_at": "2024-01-01T08:00:00", "action": "taken"}]
            },
        }
        with patch(
            "custom_components.medication_tracker.coordinator.Store"
        ) as mock_store_cls:
            mock_store = AsyncMock()
            mock_store.async_load = AsyncMock(return_value=stored_data)
            mock_store.async_save = AsyncMock()
            mock_store_cls.return_value = mock_store

            coord = MedicationCoordinator(mock_hass, "entry_id")
            coord._store = mock_store
            await coord.async_load()

        assert coord._dose_log.get("abc", []) == []


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestMedicationCRUD:
    async def test_add_medication_returns_id(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Lisinopril", "dose": "10mg", "times": ["08:00"], "days": [], "notes": ""}
            )
        assert isinstance(med_id, str)
        assert len(med_id) > 0

    async def test_add_medication_persists(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            await coordinator.async_add_medication(
                {"name": "Lisinopril", "dose": "10mg", "times": ["08:00"], "days": [], "notes": ""}
            )
        assert len(coordinator.medications) == 1
        assert coordinator.medications[0]["name"] == "Lisinopril"

    async def test_get_medication_by_id(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Metformin", "dose": "500mg", "times": [], "days": [], "notes": ""}
            )
        med = coordinator.get_medication(med_id)
        assert med is not None
        assert med["name"] == "Metformin"

    async def test_get_medication_unknown_id_returns_none(self, coordinator):
        assert coordinator.get_medication("nonexistent") is None

    async def test_update_medication(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "OldName", "dose": "5mg", "times": [], "days": [], "notes": ""}
            )
            result = await coordinator.async_update_medication(
                med_id, {"name": "NewName", "dose": "10mg", "times": [], "days": [], "notes": ""}
            )
        assert result is True
        med = coordinator.get_medication(med_id)
        assert med["name"] == "NewName"
        assert med["dose"] == "10mg"

    async def test_update_nonexistent_returns_false(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            result = await coordinator.async_update_medication("no-such-id", {"name": "X"})
        assert result is False

    async def test_remove_medication(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Temp", "dose": "", "times": [], "days": [], "notes": ""}
            )
            result = await coordinator.async_remove_medication(med_id)
        assert result is True
        assert coordinator.get_medication(med_id) is None

    async def test_remove_nonexistent_returns_false(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            result = await coordinator.async_remove_medication("no-such-id")
        assert result is False

    async def test_remove_also_clears_dose_log(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Temp", "dose": "", "times": [], "days": [], "notes": ""}
            )
            await coordinator.async_mark_taken(med_id)
            await coordinator.async_remove_medication(med_id)
        assert med_id not in coordinator._dose_log

    async def test_add_multiple_medications(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            for name in ["Med A", "Med B", "Med C"]:
                await coordinator.async_add_medication(
                    {"name": name, "dose": "", "times": [], "days": [], "notes": ""}
                )
        assert len(coordinator.medications) == 3


# ---------------------------------------------------------------------------
# Dose logging
# ---------------------------------------------------------------------------


class TestDoseLogging:
    async def test_mark_taken_returns_true(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "100mg", "times": [], "days": [], "notes": ""}
            )
            result = await coordinator.async_mark_taken(med_id)
        assert result is True

    async def test_mark_taken_unknown_returns_false(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            result = await coordinator.async_mark_taken("unknown-id")
        assert result is False

    async def test_mark_taken_increments_today_count(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "", "times": [], "days": [], "notes": ""}
            )
            await coordinator.async_mark_taken(med_id)
            await coordinator.async_mark_taken(med_id)
        state = coordinator.get_med_state(med_id)
        assert state["taken_today"] == 2

    async def test_mark_skipped_returns_true(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "", "times": [], "days": [], "notes": ""}
            )
            result = await coordinator.async_mark_skipped(med_id)
        assert result is True

    async def test_mark_skipped_increments_skipped_count(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "", "times": [], "days": [], "notes": ""}
            )
            await coordinator.async_mark_skipped(med_id, scheduled_time="08:00")
        state = coordinator.get_med_state(med_id)
        assert state["skipped_today"] == 1

    async def test_reset_today_clears_entries(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "", "times": [], "days": [], "notes": ""}
            )
            await coordinator.async_mark_taken(med_id)
            await coordinator.async_mark_skipped(med_id)
            await coordinator.async_reset_today(med_id)
        state = coordinator.get_med_state(med_id)
        assert state["taken_today"] == 0
        assert state["skipped_today"] == 0

    async def test_reset_today_unknown_returns_false(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            result = await coordinator.async_reset_today("no-such-id")
        assert result is False

    async def test_mark_taken_with_custom_time(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Aspirin", "dose": "", "times": [], "days": [], "notes": ""}
            )
            custom_time = _today_dt(7, 30)
            await coordinator.async_mark_taken(med_id, taken_at=custom_time)
        state = coordinator.get_med_state(med_id)
        assert state["last_taken"] is not None
        assert "07:30" in state["last_taken"]


# ---------------------------------------------------------------------------
# State calculation — next dose
# ---------------------------------------------------------------------------


class TestNextDoseCalculation:
    async def test_next_dose_in_future_today(self, coordinator):
        """If a scheduled time is later today, it should be the next dose."""
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Med", "dose": "", "times": ["23:59"], "days": [], "notes": ""}
            )
        state = coordinator.get_med_state(med_id)
        # Should be today's date in the next_dose value
        assert state["next_dose"] is not None
        assert "23:59" in (state["next_dose_time"] or "")

    async def test_next_dose_rolls_to_tomorrow_when_all_times_passed(self, coordinator):
        """When all today's times have passed, next dose is tomorrow."""
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Med", "dose": "", "times": ["00:01"], "days": [], "notes": ""}
            )
        state = coordinator.get_med_state(med_id)
        if state["next_dose"] is not None:
            from datetime import date
            next_dose_dt = datetime.fromisoformat(state["next_dose"])
            assert next_dose_dt.date() >= date.today()

    async def test_no_next_dose_when_no_times_configured(self, coordinator):
        with patch.object(coordinator, "_async_save", AsyncMock()):
            med_id = await coordinator.async_add_medication(
                {"name": "Med", "dose": "", "times": [], "days": [], "notes": ""}
            )
        state = coordinator.get_med_state(med_id)
        assert state["next_dose"] is None


# ---------------------------------------------------------------------------
# State calculation — overdue
# ---------------------------------------------------------------------------


class TestOverdueCalculation:
    def test_not_overdue_when_within_grace_period(self, coordinator):
        """A dose scheduled for 1 minute ago should NOT be overdue yet."""
        med = {
            "id": "x",
            "name": "Med",
            "dose": "",
            "times": [],
            "days": [],
            "notes": "",
        }
        # Construct a scheduled time 1 minute ago
        from datetime import date
        now = datetime.now(tz=timezone.utc)
        t = (now - timedelta(minutes=1)).strftime("%H:%M")
        med["times"] = [t]

        state = coordinator._build_med_state(med, now)
        assert state["is_overdue"] is False

    def test_overdue_when_past_grace_period(self, coordinator):
        """A dose from OVERDUE_GRACE_MINUTES+5 minutes ago with no log entry is overdue."""
        med = {
            "id": "x",
            "name": "Med",
            "dose": "",
            "times": [],
            "days": [],
            "notes": "",
        }
        now = datetime.now(tz=timezone.utc)
        t = (now - timedelta(minutes=OVERDUE_GRACE_MINUTES + 5)).strftime("%H:%M")
        med["times"] = [t]

        state = coordinator._build_med_state(med, now)
        assert state["is_overdue"] is True

    def test_not_overdue_when_taken(self, coordinator):
        """If the scheduled slot has been marked taken, not overdue."""
        from datetime import date
        now = datetime.now(tz=timezone.utc)
        t_str = (now - timedelta(minutes=OVERDUE_GRACE_MINUTES + 5)).strftime("%H:%M")
        med = {
            "id": "y",
            "name": "Med",
            "dose": "",
            "times": [t_str],
            "days": [],
            "notes": "",
        }
        # Inject a taken entry for this slot
        coordinator._dose_log["y"] = [
            {
                "date": date.today().isoformat(),
                "taken_at": now.isoformat(),
                "scheduled_time": t_str,
                "action": "taken",
            }
        ]
        state = coordinator._build_med_state(med, now)
        assert state["is_overdue"] is False

    def test_not_overdue_when_skipped(self, coordinator):
        """If the scheduled slot has been skipped, not overdue."""
        from datetime import date
        now = datetime.now(tz=timezone.utc)
        t_str = (now - timedelta(minutes=OVERDUE_GRACE_MINUTES + 5)).strftime("%H:%M")
        med = {
            "id": "z",
            "name": "Med",
            "dose": "",
            "times": [t_str],
            "days": [],
            "notes": "",
        }
        coordinator._dose_log["z"] = [
            {
                "date": date.today().isoformat(),
                "taken_at": None,
                "scheduled_time": t_str,
                "action": "skipped",
            }
        ]
        state = coordinator._build_med_state(med, now)
        assert state["is_overdue"] is False

    def test_not_overdue_on_non_scheduled_day(self, coordinator):
        """Medication not scheduled today should never be overdue."""
        now = datetime.now(tz=timezone.utc)
        # Schedule for a day that is not today
        today_weekday = now.weekday()
        other_day = (today_weekday + 1) % 7
        med = {
            "id": "w",
            "name": "Med",
            "dose": "",
            "times": ["00:01"],
            "days": [other_day],
            "notes": "",
        }
        state = coordinator._build_med_state(med, now)
        assert state["is_overdue"] is False


# ---------------------------------------------------------------------------
# State calculation — streak
# ---------------------------------------------------------------------------


class TestStreakCalculation:
    def test_streak_zero_with_no_entries(self, coordinator):
        from datetime import date
        assert coordinator._calculate_streak("no-id", date.today()) == 0

    def test_streak_one_for_today_only(self, coordinator):
        from datetime import date
        today = date.today()
        coordinator._dose_log["med1"] = [
            {"date": today.isoformat(), "taken_at": "08:00:00", "action": "taken"}
        ]
        assert coordinator._calculate_streak("med1", today) == 1

    def test_streak_counts_consecutive_days(self, coordinator):
        from datetime import date
        today = date.today()
        coordinator._dose_log["med2"] = [
            {"date": (today - timedelta(days=i)).isoformat(), "taken_at": "08:00:00", "action": "taken"}
            for i in range(5)
        ]
        assert coordinator._calculate_streak("med2", today) == 5

    def test_streak_breaks_on_missed_day(self, coordinator):
        from datetime import date
        today = date.today()
        # Taken today and 2 days ago, but not yesterday
        coordinator._dose_log["med3"] = [
            {"date": today.isoformat(), "taken_at": "08:00:00", "action": "taken"},
            {"date": (today - timedelta(days=2)).isoformat(), "taken_at": "08:00:00", "action": "taken"},
        ]
        assert coordinator._calculate_streak("med3", today) == 1

    def test_streak_ignores_skipped_entries(self, coordinator):
        from datetime import date
        today = date.today()
        # Skipped today — should not count toward streak
        coordinator._dose_log["med4"] = [
            {"date": today.isoformat(), "taken_at": None, "action": "skipped"}
        ]
        assert coordinator._calculate_streak("med4", today) == 0


# ---------------------------------------------------------------------------
# Due soon
# ---------------------------------------------------------------------------


class TestDueSoonCalculation:
    def test_due_soon_within_window(self, coordinator):
        now = datetime.now(tz=timezone.utc)
        t_str = (now + timedelta(minutes=30)).strftime("%H:%M")
        med = {"id": "a", "name": "Med", "dose": "", "times": [t_str], "days": [], "notes": ""}
        state = coordinator._build_med_state(med, now)
        assert state["is_due_soon"] is True

    def test_not_due_soon_far_in_future(self, coordinator):
        now = datetime.now(tz=timezone.utc)
        t_str = (now + timedelta(hours=3)).strftime("%H:%M")
        med = {"id": "b", "name": "Med", "dose": "", "times": [t_str], "days": [], "notes": ""}
        state = coordinator._build_med_state(med, now)
        assert state["is_due_soon"] is False


# ---------------------------------------------------------------------------
# Days filtering
# ---------------------------------------------------------------------------


class TestDaysFiltering:
    def test_scheduled_today_with_empty_days(self, coordinator):
        """Empty days list means every day."""
        now = datetime.now(tz=timezone.utc)
        med = {"id": "a", "name": "Med", "dose": "", "times": [], "days": [], "notes": ""}
        state = coordinator._build_med_state(med, now)
        assert state["scheduled_today"] is True

    def test_not_scheduled_on_excluded_day(self, coordinator):
        """Medication scheduled on specific days should show not scheduled on others."""
        now = datetime.now(tz=timezone.utc)
        today_weekday = now.weekday()
        other_days = [(today_weekday + i) % 7 for i in range(1, 7)]
        med = {"id": "b", "name": "Med", "dose": "", "times": [], "days": other_days, "notes": ""}
        state = coordinator._build_med_state(med, now)
        assert state["scheduled_today"] is False
        assert state["doses_scheduled_today"] == 0
