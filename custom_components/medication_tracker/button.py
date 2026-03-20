"""Button platform for Medication Tracker."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SUFFIX_MARK_SKIPPED,
    SUFFIX_MARK_TAKEN,
)
from .coordinator import MedicationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for each medication."""
    coordinator: MedicationCoordinator = entry.runtime_data
    entities: list[ButtonEntity] = []
    for med in coordinator.medications:
        entities += _buttons_for_med(coordinator, entry.entry_id, med["id"])
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
    new_entities: list[ButtonEntity] = []
    for med in coordinator.medications:
        if med["id"] not in known:
            new_entities += _buttons_for_med(coordinator, entry.entry_id, med["id"])
    if new_entities:
        async_add_entities(new_entities)


def _buttons_for_med(
    coordinator: MedicationCoordinator, entry_id: str, med_id: str
) -> list[ButtonEntity]:
    _tracked_med_ids.setdefault(entry_id, set()).add(med_id)
    return [
        MedicationMarkTakenButton(coordinator, entry_id, med_id),
        MedicationMarkSkippedButton(coordinator, entry_id, med_id),
    ]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class MedicationBaseButton(ButtonEntity):
    """Base button for medication actions."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MedicationCoordinator,
        entry_id: str,
        med_id: str,
        suffix: str,
    ) -> None:
        self._coordinator = coordinator
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
        med = self._coordinator.get_medication(self._med_id)
        return med["name"] if med else "Unknown"

    @property
    def available(self) -> bool:
        return bool(self._coordinator.get_medication(self._med_id))


# ---------------------------------------------------------------------------
# Mark taken
# ---------------------------------------------------------------------------


class MedicationMarkTakenButton(MedicationBaseButton):
    """Button to mark a medication dose as taken."""

    _attr_icon = "mdi:pill"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_MARK_TAKEN)

    @property
    def name(self) -> str:
        return "Mark taken"

    async def async_press(self) -> None:
        """Handle button press — mark dose taken with correct scheduled_time."""
        state = self._coordinator.get_med_state(self._med_id)
        scheduled_time = None
        if state.get("is_overdue") and state.get("overdue_since"):
            try:
                from datetime import datetime
                overdue_dt = datetime.fromisoformat(state["overdue_since"])
                scheduled_time = overdue_dt.strftime("%H:%M")
            except (ValueError, KeyError):
                pass
        await self._coordinator.async_mark_taken(
            self._med_id, scheduled_time=scheduled_time
        )


# ---------------------------------------------------------------------------
# Mark skipped
# ---------------------------------------------------------------------------


class MedicationMarkSkippedButton(MedicationBaseButton):
    """Button to mark a medication dose as skipped."""

    _attr_icon = "mdi:pill-off"

    def __init__(
        self, coordinator: MedicationCoordinator, entry_id: str, med_id: str
    ) -> None:
        super().__init__(coordinator, entry_id, med_id, SUFFIX_MARK_SKIPPED)

    @property
    def name(self) -> str:
        return "Mark skipped"

    async def async_press(self) -> None:
        """Handle button press — mark dose skipped with correct scheduled_time."""
        state = self._coordinator.get_med_state(self._med_id)
        scheduled_time = None
        if state.get("overdue_since"):
            try:
                from datetime import datetime
                overdue_dt = datetime.fromisoformat(state["overdue_since"])
                scheduled_time = overdue_dt.strftime("%H:%M")
            except (ValueError, KeyError):
                pass
        await self._coordinator.async_mark_skipped(
            self._med_id, scheduled_time=scheduled_time
        )
