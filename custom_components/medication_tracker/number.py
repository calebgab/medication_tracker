"""Number platform for Medication Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_STOCK,
    DOMAIN,
    SUFFIX_STOCK_NUMBER,
)
from .coordinator import MedicationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for each medication."""
    coordinator: MedicationCoordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    for med in coordinator.medications:
        entities += _numbers_for_med(coordinator, entry.entry_id, med["id"])
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
    """Add number entities for any newly added medications."""
    known = _tracked_med_ids.setdefault(entry.entry_id, set())
    new_entities: list[NumberEntity] = []
    for med in coordinator.medications:
        if med["id"] not in known:
            new_entities += _numbers_for_med(coordinator, entry.entry_id, med["id"])
    if new_entities:
        async_add_entities(new_entities)


def _numbers_for_med(
    coordinator: MedicationCoordinator, entry_id: str, med_id: str
) -> list[NumberEntity]:
    """Return all number entities for a single medication."""
    _tracked_med_ids.setdefault(entry_id, set()).add(med_id)
    return [MedicationStockNumber(coordinator, entry_id, med_id)]


# ---------------------------------------------------------------------------
# Stock number — directly settable, so stock can be topped up without
# re-opening the edit-medication form or calling a service by hand.
# ---------------------------------------------------------------------------


class MedicationStockNumber(CoordinatorEntity[MedicationCoordinator], NumberEntity):
    """Editable control for a medication's current stock level."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:package-variant"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator)
        self._med_id = med_id
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_{med_id}_{SUFFIX_STOCK_NUMBER}"
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
    def name(self) -> str:
        return "Stock"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and bool(self.coordinator.get_medication(self._med_id))
            and bool(self._state_data.get("stock_tracking_enabled"))
        )

    @property
    def native_value(self) -> float | None:
        return self._state_data.get(ATTR_CURRENT_STOCK)

    async def async_set_native_value(self, value: float) -> None:
        """Set the stock to an absolute value — e.g. after a refill."""
        await self.coordinator.async_set_stock(self._med_id, value)
