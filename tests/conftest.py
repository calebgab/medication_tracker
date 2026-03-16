"""Shared fixtures for Medication Tracker tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.medication_tracker.coordinator import MedicationCoordinator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MED_ID = "test-med-id-0001"
SAMPLE_MED_ID_2 = "test-med-id-0002"

SAMPLE_MED: dict[str, Any] = {
    "id": SAMPLE_MED_ID,
    "name": "Aspirin",
    "dose": "100mg",
    "times": ["08:00", "20:00"],
    "days": [],
    "notes": "Take with food",
}

SAMPLE_MED_2: dict[str, Any] = {
    "id": SAMPLE_MED_ID_2,
    "name": "Vitamin D",
    "dose": "1000IU",
    "times": ["09:00"],
    "days": [0, 1, 2, 3, 4],  # Weekdays only
    "notes": "",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_hass():
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.loop = MagicMock()
    hass.config_entries = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    return hass


@pytest.fixture
async def coordinator(mock_hass):
    """Return a MedicationCoordinator with mocked storage."""
    with patch(
        "custom_components.medication_tracker.coordinator.Store"
    ) as mock_store_cls:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()
        mock_store_cls.return_value = mock_store

        coord = MedicationCoordinator(mock_hass, "test_entry_id")
        coord._store = mock_store
        await coord.async_load()
        return coord


@pytest.fixture
async def coordinator_with_meds(coordinator):
    """Return a coordinator pre-loaded with sample medications."""
    with patch.object(coordinator, "_async_save", AsyncMock()):
        await coordinator.async_add_medication(
            {
                "name": SAMPLE_MED["name"],
                "dose": SAMPLE_MED["dose"],
                "times": SAMPLE_MED["times"],
                "days": SAMPLE_MED["days"],
                "notes": SAMPLE_MED["notes"],
            }
        )
        await coordinator.async_add_medication(
            {
                "name": SAMPLE_MED_2["name"],
                "dose": SAMPLE_MED_2["dose"],
                "times": SAMPLE_MED_2["times"],
                "days": SAMPLE_MED_2["days"],
                "notes": SAMPLE_MED_2["notes"],
            }
        )
    return coordinator


def make_aware_dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Return a timezone-aware datetime in UTC."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
