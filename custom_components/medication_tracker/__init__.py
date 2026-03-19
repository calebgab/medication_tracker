"""Medication Tracker integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_MEDICATION_ID,
    ATTR_SCHEDULED_TIME,
    ATTR_TAKEN_AT,
    DOMAIN,
    PLATFORMS,
    SERVICE_MARK_SKIPPED,
    SERVICE_MARK_TAKEN,
    SERVICE_RESET_TODAY,
)
from .coordinator import MedicationCoordinator
from .notify import MedicationNotifier

_LOGGER = logging.getLogger(__name__)

type MedicationTrackerConfigEntry = ConfigEntry[MedicationCoordinator]

# ---------------------------------------------------------------------------
# Service schemas
# ---------------------------------------------------------------------------

_SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDICATION_ID): cv.string,
    }
)

_MARK_TAKEN_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_SCHEDULED_TIME): cv.string,
        vol.Optional(ATTR_TAKEN_AT): cv.string,
    }
)

_MARK_SKIPPED_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_SCHEDULED_TIME): cv.string,
    }
)

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: MedicationTrackerConfigEntry) -> bool:
    """Set up Medication Tracker from a config entry."""
    coordinator = MedicationCoordinator(hass, entry.entry_id)
    await coordinator.async_load()

    notifier = MedicationNotifier(hass, coordinator)
    coordinator._notifier = notifier

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MedicationTrackerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    remaining = [
        e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id
    ]
    if not remaining:
        for svc in (SERVICE_MARK_TAKEN, SERVICE_MARK_SKIPPED, SERVICE_RESET_TODAY):
            if hass.services.has_service(DOMAIN, svc):
                hass.services.async_remove(DOMAIN, svc)

    return unload_ok

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def _get_coordinator(hass: HomeAssistant, med_id: str) -> MedicationCoordinator:
    """Find the coordinator that owns this medication id."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator: MedicationCoordinator = entry.runtime_data
        if coordinator.get_medication(med_id):
            return coordinator
    raise ServiceValidationError(
        f"Medication with id '{med_id}' not found in any Medication Tracker entry."
    )


def _register_services(hass: HomeAssistant, entry: MedicationTrackerConfigEntry) -> None:
    """Register HA services (idempotent — only registers once)."""
    if hass.services.has_service(DOMAIN, SERVICE_MARK_TAKEN):
        return

    async def handle_mark_taken(call: ServiceCall) -> None:
        med_id: str = call.data[ATTR_MEDICATION_ID]
        scheduled_time: str | None = call.data.get(ATTR_SCHEDULED_TIME)
        taken_at_raw: str | None = call.data.get(ATTR_TAKEN_AT)
        taken_at = None
        if taken_at_raw:
            from homeassistant.util.dt import parse_datetime
            taken_at = parse_datetime(taken_at_raw)
        coordinator = _get_coordinator(hass, med_id)
        success = await coordinator.async_mark_taken(
            med_id, taken_at=taken_at, scheduled_time=scheduled_time
        )
        if not success:
            raise ServiceValidationError(f"Could not mark medication '{med_id}' as taken.")

    async def handle_mark_skipped(call: ServiceCall) -> None:
        med_id: str = call.data[ATTR_MEDICATION_ID]
        scheduled_time: str | None = call.data.get(ATTR_SCHEDULED_TIME)
        coordinator = _get_coordinator(hass, med_id)
        success = await coordinator.async_mark_skipped(med_id, scheduled_time=scheduled_time)
        if not success:
            raise ServiceValidationError(f"Could not mark medication '{med_id}' as skipped.")

    async def handle_reset_today(call: ServiceCall) -> None:
        med_id: str = call.data[ATTR_MEDICATION_ID]
        coordinator = _get_coordinator(hass, med_id)
        success = await coordinator.async_reset_today(med_id)
        if not success:
            raise ServiceValidationError(
                f"Could not reset today's log for medication '{med_id}'."
            )

    hass.services.async_register(
        DOMAIN, SERVICE_MARK_TAKEN, handle_mark_taken, schema=_MARK_TAKEN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_SKIPPED, handle_mark_skipped, schema=_MARK_SKIPPED_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_TODAY, handle_reset_today, schema=_SERVICE_BASE_SCHEMA
    )
