"""Tests for the Medication Tracker config and options flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.medication_tracker.config_flow import (
    MedicationOptionsFlow,
    MedicationTrackerConfigFlow,
    _validate_days,
    _validate_times,
)


# ---------------------------------------------------------------------------
# Time/day validators
# ---------------------------------------------------------------------------


class TestValidateTimes:
    def test_single_valid_time(self):
        assert _validate_times("08:00") == ["08:00"]

    def test_multiple_valid_times(self):
        assert _validate_times("08:00, 12:00, 20:00") == ["08:00", "12:00", "20:00"]

    def test_empty_string_returns_empty(self):
        assert _validate_times("") == []

    def test_invalid_time_raises(self):
        with pytest.raises(vol.Invalid):
            _validate_times("8:00")  # no leading zero

    def test_invalid_time_raises_letters(self):
        with pytest.raises(vol.Invalid):
            _validate_times("morning")

    def test_whitespace_stripped(self):
        assert _validate_times("  08:00  ,  20:00  ") == ["08:00", "20:00"]


class TestValidateDays:
    def test_empty_returns_empty(self):
        assert _validate_days("") == []

    def test_named_days(self):
        result = _validate_days("mon, wed, fri")
        assert result == [0, 2, 4]

    def test_numeric_days(self):
        result = _validate_days("0,1,2")
        assert result == [0, 1, 2]

    def test_mixed_case(self):
        assert _validate_days("MON, TUE") == [0, 1]

    def test_full_week(self):
        result = _validate_days("mon,tue,wed,thu,fri,sat,sun")
        assert result == [0, 1, 2, 3, 4, 5, 6]

    def test_deduplicates(self):
        result = _validate_days("mon,mon,tue")
        assert result == [0, 1]

    def test_invalid_day_raises(self):
        with pytest.raises(vol.Invalid):
            _validate_days("monday")  # full name not supported

    def test_invalid_number_raises(self):
        with pytest.raises(vol.Invalid):
            _validate_days("7")  # out of range


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


class TestMedicationConfigFlow:
    async def test_user_step_creates_entry(self):
        flow = MedicationTrackerConfigFlow()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_set_unique_id = AsyncMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

        result = await flow.async_step_user({"title": "My Meds"})
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args
        assert call_kwargs[1]["title"] == "My Meds"

    async def test_user_step_defaults_title(self):
        flow = MedicationTrackerConfigFlow()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_set_unique_id = AsyncMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

        result = await flow.async_step_user({"title": ""})
        call_kwargs = flow.async_create_entry.call_args
        assert call_kwargs[1]["title"] == "Medication Tracker"

    async def test_user_step_shows_form_when_no_input(self):
        flow = MedicationTrackerConfigFlow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        result = await flow.async_step_user(None)
        flow.async_show_form.assert_called_once()
        assert result == {"type": "form"}


# ---------------------------------------------------------------------------
# Options flow — add medication
# ---------------------------------------------------------------------------


class TestOptionsFlowAdd:
    def _make_options_flow(self, meds=None):
        """Build an options flow with a mocked config entry and coordinator."""
        coordinator = MagicMock()
        coordinator.medications = meds or []
        coordinator.get_medication = MagicMock(return_value=None)
        coordinator.async_add_medication = AsyncMock()
        coordinator.async_update_medication = AsyncMock(return_value=True)
        coordinator.async_remove_medication = AsyncMock(return_value=True)

        entry = MagicMock()
        entry.runtime_data = coordinator

        flow = MedicationOptionsFlow(entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        return flow, coordinator

    async def test_init_shows_form_with_no_input(self):
        flow, _ = self._make_options_flow()
        result = await flow.async_step_init(None)
        flow.async_show_form.assert_called_once()

    async def test_init_done_creates_entry(self):
        flow, _ = self._make_options_flow()
        result = await flow.async_step_init({"action": "done"})
        flow.async_create_entry.assert_called_once()

    async def test_init_add_redirects_to_add_step(self):
        flow, _ = self._make_options_flow()
        flow.async_step_add_medication = AsyncMock(return_value={"type": "form"})
        result = await flow.async_step_init({"action": "add"})
        flow.async_step_add_medication.assert_called_once()

    async def test_init_remove_redirects_to_remove_step(self):
        flow, _ = self._make_options_flow()
        flow.async_step_remove_medication = AsyncMock(return_value={"type": "form"})
        result = await flow.async_step_init({"action": "remove"})
        flow.async_step_remove_medication.assert_called_once()

    async def test_add_medication_valid_input_calls_coordinator(self):
        flow, coordinator = self._make_options_flow()
        flow.async_step_init = AsyncMock(return_value={"type": "form"})

        await flow.async_step_add_medication(
            {
                "name": "Aspirin",
                "dose": "100mg",
                "times": "08:00, 20:00",
                "days": "mon, wed, fri",
                "notes": "Take with food",
            }
        )
        coordinator.async_add_medication.assert_called_once()
        call_data = coordinator.async_add_medication.call_args[0][0]
        assert call_data["name"] == "Aspirin"
        assert call_data["times"] == ["08:00", "20:00"]
        assert call_data["days"] == [0, 2, 4]

    async def test_add_medication_invalid_time_shows_error(self):
        flow, coordinator = self._make_options_flow()

        result = await flow.async_step_add_medication(
            {
                "name": "Aspirin",
                "dose": "",
                "times": "not-a-time",
                "days": "",
                "notes": "",
            }
        )
        coordinator.async_add_medication.assert_not_called()
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert "times" in call_kwargs["errors"]

    async def test_add_medication_invalid_days_shows_error(self):
        flow, coordinator = self._make_options_flow()

        result = await flow.async_step_add_medication(
            {
                "name": "Aspirin",
                "dose": "",
                "times": "08:00",
                "days": "monday",
                "notes": "",
            }
        )
        coordinator.async_add_medication.assert_not_called()
        call_kwargs = flow.async_show_form.call_args[1]
        assert "days" in call_kwargs["errors"]

    async def test_remove_shows_form_with_medications(self):
        flow, coordinator = self._make_options_flow(
            meds=[{"id": "abc", "name": "Aspirin"}]
        )
        result = await flow.async_step_remove_medication(None)
        flow.async_show_form.assert_called_once()

    async def test_remove_skips_to_init_when_no_meds(self):
        flow, coordinator = self._make_options_flow(meds=[])
        flow.async_step_init = AsyncMock(return_value={"type": "form"})
        result = await flow.async_step_remove_medication(None)
        flow.async_step_init.assert_called_once()

    async def test_remove_calls_coordinator(self):
        flow, coordinator = self._make_options_flow(
            meds=[{"id": "abc", "name": "Aspirin"}]
        )
        flow.async_step_init = AsyncMock(return_value={"type": "form"})
        await flow.async_step_remove_medication({"medication_id": "abc"})
        coordinator.async_remove_medication.assert_called_once_with("abc")
