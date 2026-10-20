"""Serves the bundled Lovelace card and loads it into every dashboard."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_FILENAME = "medication-tracker-card.js"
CARD_URL = f"/api/{DOMAIN}/{CARD_FILENAME}"
CARD_FILE = Path(__file__).parent / "www" / CARD_FILENAME


async def async_register_card(hass: HomeAssistant) -> None:
    """Expose the card file and tell the frontend to load it.

    The integration version is appended to the URL so browsers fetch the new
    file after an update instead of serving a cached copy.
    """
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
