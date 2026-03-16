"""Sensor platform for Medication Tracker."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_DOSE,
    ATTR_LAST_TAKEN,
    ATTR_NEXT_DOSE,
    ATTR_NOTES,
    ATTR_SCHEDULED_TIME,
    ATTR_SKIPPED_TODAY,
    ATTR_STREAK,
    ATTR_TAKEN_TODAY,
    ATTR_TIMES,
    DOMAIN,
    SUFFIX_LAST_TAKEN,
    SUFFIX_NEXT_DOSE,
    SUFFIX_STREAK,
    SUFFIX_TAKEN_TODAY,
)
from .coordinator import MedicationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each medication."""
    coordinator: MedicationCoordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for med in coordinator.medications:
        entities += _sensors_for_med(coordinator, entry.entry_id, med["id"])
    async_add_entities(entities)

    # Dynamic addition when medications are added via options flow
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _async_update_entities(hass, coordinator, entry, async_add_entities)
        )
    )


_tracked_med_ids: dict[str, set[str]] = {}


def _async_update_entities(
    hass: HomeAssistant,
    coordinator: MedicationCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for any newly added medications."""
    known = _tracked_med_ids.setdefault(entry.entry_id, set())
    new_entities: list[SensorEntity] = []
    for med in coordinator.medications:
        if med["id"] not in known:
            new_entities += _sensors_for_med(coordinator, entry.entry_id, med["id"])
    if new_entities:
        async_add_entities(new_entities)


def _sensors_for_med(
    coordinator: MedicationCoordinator, entry_id: str, med_id: str
) -> list[SensorEntity]:
    """Return all sensor entities for a single medication."""
    _tracked_med_ids.setdefault(entry_id, set()).add(med_id)
    return [
        MedicationNextDoseSensor(coordinator, entry_id, med_id),
        MedicationLastTakenSensor(coordinator, entry_id, med_id),
        MedicationStreakSensor(coordinator, entry_id, med_id),
        MedicationTakenTodaySensor(coordinator, entry_id, med_id),
    ]


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class MedicationBaseSensor(CoordinatorEntity[MedicationCoordinator], SensorEntity):
    """Base class for medication sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MedicationCoordinator,
        entry_id: str,
        med_id: str,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._med_id = med_id
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_{med_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{med_id}")},
            name=self._med_name,
            manufacturer="Medication Tracker",
        )

    @property
    def _med_name(self) -> str:
        med = self.coordinator.get_medication(self._med_id)
        return med["name"] if med else "Unknown"

    @property
    def _state_data(self) -> dict[str, Any]:
        return self.coordinator.get_med_state(self._med_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.get_medication(self._med_id)
        )


# ---------------------------------------------------------------------------
# Next dose sensor
# ---------------------------------------------------------------------------


class MedicationNextDoseSensor(MedicationBaseSensor):
    """Sensor showing the next scheduled dose time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_dose"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_NEXT_DOSE)

    @property
    def name(self) -> str:
        return f"{self._med_name} Next Dose"

    @property
    def native_value(self) -> datetime | None:
        next_dose_str = self._state_data.get(ATTR_NEXT_DOSE)
        if next_dose_str:
            return dt_util.parse_datetime(next_dose_str)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._state_data
        return {
            ATTR_TIMES: data.get(ATTR_TIMES, []),
            ATTR_SCHEDULED_TIME: data.get("next_dose_time"),
            ATTR_DOSE: data.get(ATTR_DOSE, ""),
            ATTR_NOTES: data.get(ATTR_NOTES, ""),
        }


# ---------------------------------------------------------------------------
# Last taken sensor
# ---------------------------------------------------------------------------


class MedicationLastTakenSensor(MedicationBaseSensor):
    """Sensor showing when the medication was last taken."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_taken"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_LAST_TAKEN)

    @property
    def name(self) -> str:
        return f"{self._med_name} Last Taken"

    @property
    def native_value(self) -> datetime | None:
        last_taken_str = self._state_data.get(ATTR_LAST_TAKEN)
        if last_taken_str:
            return dt_util.parse_datetime(last_taken_str)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._state_data
        return {
            ATTR_TAKEN_TODAY: data.get(ATTR_TAKEN_TODAY, 0),
            ATTR_SKIPPED_TODAY: data.get(ATTR_SKIPPED_TODAY, 0),
            ATTR_DOSE: data.get(ATTR_DOSE, ""),
        }


# ---------------------------------------------------------------------------
# Streak sensor
# ---------------------------------------------------------------------------


class MedicationStreakSensor(MedicationBaseSensor):
    """Sensor showing consecutive days with at least one dose taken."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "days"
    _attr_translation_key = "streak"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_STREAK)

    @property
    def name(self) -> str:
        return f"{self._med_name} Streak"

    @property
    def native_value(self) -> int:
        return self._state_data.get(ATTR_STREAK, 0)

    @property
    def icon(self) -> str:
        streak = self.native_value
        if streak >= 30:
            return "mdi:fire-circle"
        if streak >= 7:
            return "mdi:fire"
        return "mdi:pill"


# ---------------------------------------------------------------------------
# Taken today sensor
# ---------------------------------------------------------------------------


class MedicationTakenTodaySensor(MedicationBaseSensor):
    """Sensor showing how many doses have been taken today."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "doses"
    _attr_icon = "mdi:pill-multiple"
    _attr_translation_key = "taken_today"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_TAKEN_TODAY)

    @property
    def name(self) -> str:
        return f"{self._med_name} Taken Today"

    @property
    def native_value(self) -> int:
        return self._state_data.get(ATTR_TAKEN_TODAY, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._state_data
        return {
            "doses_scheduled_today": data.get("doses_scheduled_today", 0),
            ATTR_SKIPPED_TODAY: data.get(ATTR_SKIPPED_TODAY, 0),
            "scheduled_today": data.get("scheduled_today", True),
        }
