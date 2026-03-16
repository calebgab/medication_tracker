"""Tests for integration __init__ (setup/unload/services)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.exceptions import ServiceValidationError

from custom_components.medication_tracker import (
    _get_coordinator,
    _register_services,
    async_unload_entry,
)
from custom_components.medication_tracker.const import (
    DOMAIN,
    SERVICE_MARK_SKIPPED,
    SERVICE_MARK_TAKEN,
    SERVICE_RESET_TODAY,
)


# ---------------------------------------------------------------------------
# _get_coordinator helper
# ---------------------------------------------------------------------------


class TestGetCoordinator:
    def _make_hass(self, entries):
        hass = MagicMock()
        hass.config_entries.async_entries = MagicMock(return_value=entries)
        return hass

    def test_finds_coordinator_by_med_id(self):
        coordinator = MagicMock()
        coordinator.get_medication = MagicMock(return_value={"id": "abc", "name": "Aspirin"})
        entry = MagicMock()
        entry.runtime_data = coordinator
        hass = self._make_hass([entry])

        result = _get_coordinator(hass, "abc")
        assert result is coordinator

    def test_raises_when_med_not_found(self):
        coordinator = MagicMock()
        coordinator.get_medication = MagicMock(return_value=None)
        entry = MagicMock()
        entry.runtime_data = coordinator
        hass = self._make_hass([entry])

        with pytest.raises(ServiceValidationError):
            _get_coordinator(hass, "nonexistent")

    def test_raises_when_no_entries(self):
        hass = self._make_hass([])
        with pytest.raises(ServiceValidationError):
            _get_coordinator(hass, "abc")


# ---------------------------------------------------------------------------
# Service registration
# ---------------------------------------------------------------------------


class TestServiceRegistration:
    def _make_hass(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        hass.services.async_register = MagicMock()
        hass.config_entries.async_entries = MagicMock(return_value=[])
        return hass

    def test_registers_all_three_services(self):
        hass = self._make_hass()
        entry = MagicMock()
        _register_services(hass, entry)

        registered = [c[0][1] for c in hass.services.async_register.call_args_list]
        assert SERVICE_MARK_TAKEN in registered
        assert SERVICE_MARK_SKIPPED in registered
        assert SERVICE_RESET_TODAY in registered

    def test_does_not_register_twice(self):
        hass = self._make_hass()
        hass.services.has_service = MagicMock(return_value=True)
        entry = MagicMock()
        _register_services(hass, entry)

        hass.services.async_register.assert_not_called()


# ---------------------------------------------------------------------------
# Unload
# ---------------------------------------------------------------------------


class TestAsyncUnloadEntry:
    async def test_unload_calls_platform_unload(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries = MagicMock(return_value=[])
        hass.services.has_service = MagicMock(return_value=True)
        hass.services.async_remove = MagicMock()

        entry = MagicMock()
        entry.entry_id = "test_entry"

        result = await async_unload_entry(hass, entry)
        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_services_removed_when_last_entry(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries = MagicMock(return_value=[])
        hass.services.has_service = MagicMock(return_value=True)
        hass.services.async_remove = MagicMock()

        entry = MagicMock()
        entry.entry_id = "test_entry"

        await async_unload_entry(hass, entry)

        removed = [c[0][1] for c in hass.services.async_remove.call_args_list]
        assert SERVICE_MARK_TAKEN in removed
        assert SERVICE_MARK_SKIPPED in removed
        assert SERVICE_RESET_TODAY in removed

    async def test_services_not_removed_when_other_entries_exist(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        hass.config_entries.async_entries = MagicMock(return_value=[other_entry])
        hass.services.has_service = MagicMock(return_value=True)
        hass.services.async_remove = MagicMock()

        entry = MagicMock()
        entry.entry_id = "test_entry"

        await async_unload_entry(hass, entry)
        hass.services.async_remove.assert_not_called()
