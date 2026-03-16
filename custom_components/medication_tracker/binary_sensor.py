"""Binary sensor platform for Medication Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DOSE,
    ATTR_NEXT_DOSE,
    ATTR_NOTES,
    ATTR_TIMES,
    DOMAIN,
    SUFFIX_DUE,
    SUFFIX_OVERDUE,
)
from .coordinator import MedicationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for each medication."""
    coordinator: MedicationCoordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for med in coordinator.medications:
        entities += _binary_sensors_for_med(coordinator, entry.entry_id, med["id"])
    async_add_entities(entities)

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
    known = _tracked_med_ids.setdefault(entry.entry_id, set())
    new_entities: list[BinarySensorEntity] = []
    for med in coordinator.medications:
        if med["id"] not in known:
            new_entities += _binary_sensors_for_med(coordinator, entry.entry_id, med["id"])
    if new_entities:
        async_add_entities(new_entities)


def _binary_sensors_for_med(
    coordinator: MedicationCoordinator, entry_id: str, med_id: str
) -> list[BinarySensorEntity]:
    _tracked_med_ids.setdefault(entry_id, set()).add(med_id)
    return [
        MedicationOverdueSensor(coordinator, entry_id, med_id),
        MedicationDueSoonSensor(coordinator, entry_id, med_id),
    ]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class MedicationBaseBinarySensor(CoordinatorEntity[MedicationCoordinator], BinarySensorEntity):
    """Base binary sensor for medication tracking."""

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
# Overdue sensor
# ---------------------------------------------------------------------------


class MedicationOverdueSensor(MedicationBaseBinarySensor):
    """Binary sensor: True when a dose is overdue (past scheduled time + grace)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: MedicationCoordinator, entry_id: str, med_id: str) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_OVERDUE)

    @property
    def name(self) -> str:
        return f"{self._med_name} Overdue"

    @property
    def is_on(self) -> bool:
        return bool(self._state_data.get("is_overdue", False))

    @property
    def icon(self) -> str:
        return "mdi:pill-off" if self.is_on else "mdi:pill"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._state_data
        return {
            "overdue_since": data.get("overdue_since"),
            ATTR_DOSE: data.get(ATTR_DOSE, ""),
            ATTR_TIMES: data.get(ATTR_TIMES, []),
            ATTR_NOTES: data.get(ATTR_NOTES, ""),
        }


# ---------------------------------------------------------------------------
# Due soon sensor
# ---------------------------------------------------------------------------


class MedicationDueSoonSensor(MedicationBaseBinarySensor):
    """Binary sensor: True when the next dose is within 60 minutes."""

    def __init__(self, coordinator: MedicationCoordinator, entry_id: str, med_id: str) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_DUE)

    @property
    def name(self) -> str:
        return f"{self._med_name} Due Soon"

    @property
    def is_on(self) -> bool:
        return bool(self._state_data.get("is_due_soon", False))

    @property
    def icon(self) -> str:
        return "mdi:bell-ring" if self.is_on else "mdi:bell-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._state_data
        return {
            ATTR_NEXT_DOSE: data.get(ATTR_NEXT_DOSE),
            "next_dose_time": data.get("next_dose_time"),
            ATTR_DOSE: data.get(ATTR_DOSE, ""),
        }
