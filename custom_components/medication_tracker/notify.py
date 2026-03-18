"""Notification engine for Medication Tracker."""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_NOTIF_DUE_SOON_ENABLED,
    CONF_NOTIF_DUE_SOON_MESSAGE,
    CONF_NOTIF_DUE_SOON_TITLE,
    CONF_NOTIF_OVERDUE_DELAY,
    CONF_NOTIF_OVERDUE_ENABLED,
    CONF_NOTIF_OVERDUE_MESSAGE,
    CONF_NOTIF_OVERDUE_TITLE,
    CONF_NOTIF_OVERRIDE_DUE_SOON,
    CONF_NOTIF_OVERRIDE_OVERDUE,
    CONF_NOTIF_OVERRIDE_TAKEN,
    CONF_NOTIF_OVERRIDES,
    CONF_NOTIF_TAKEN_ENABLED,
    CONF_NOTIF_TAKEN_MESSAGE,
    CONF_NOTIF_TAKEN_TITLE,
    CONF_NOTIF_TARGET,
    DEFAULT_DUE_SOON_MESSAGE,
    DEFAULT_DUE_SOON_TITLE,
    DEFAULT_NOTIFY_TARGET,
    DEFAULT_OVERDUE_DELAY,
    DEFAULT_OVERDUE_MESSAGE,
    DEFAULT_OVERDUE_TITLE,
    DEFAULT_TAKEN_MESSAGE,
    DEFAULT_TAKEN_TITLE,
)

if TYPE_CHECKING:
    from .coordinator import MedicationCoordinator

_LOGGER = logging.getLogger(__name__)


class MedicationNotifier:
    """Fires HA notifications based on medication state changes."""

    def __init__(self, hass: HomeAssistant, coordinator: MedicationCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        # Tracks which notifications have already fired today to prevent repeats.
        # Keys: "{med_id}_{event}_{slot}" e.g. "abc_overdue_08:00", "abc_due_soon_08:00"
        self._fired: set[str] = set()
        self._fired_date: date = date.today()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def async_check_and_notify(self) -> None:
        """Called each coordinator tick — check state and fire pending notifications."""
        self._reset_if_new_day()
        notif_config = self._coordinator.notification_config

        for med in self._coordinator.medications:
            med_id = med["id"]
            state = self._coordinator.get_med_state(med_id)
            overrides = med.get(CONF_NOTIF_OVERRIDES, {})

            await self._check_overdue(med, state, notif_config, overrides)
            await self._check_due_soon(med, state, notif_config, overrides)

    async def async_notify_taken(self, med_id: str) -> None:
        """Called immediately when a dose is marked taken."""
        self._reset_if_new_day()
        notif_config = self._coordinator.notification_config
        med = self._coordinator.get_medication(med_id)
        if not med:
            return

        overrides = med.get(CONF_NOTIF_OVERRIDES, {})
        enabled = overrides.get(
            CONF_NOTIF_OVERRIDE_TAKEN,
            notif_config.get(CONF_NOTIF_TAKEN_ENABLED, False),
        )
        if not enabled:
            return

        state = self._coordinator.get_med_state(med_id)
        title = notif_config.get(CONF_NOTIF_TAKEN_TITLE, DEFAULT_TAKEN_TITLE)
        message = notif_config.get(CONF_NOTIF_TAKEN_MESSAGE, DEFAULT_TAKEN_MESSAGE)
        await self._send(
            notif_config,
            title,
            message,
            {
                "medication": med["name"],
                "dose": med.get("dose", ""),
                "time": state.get("next_dose_time", ""),
                "overdue_since": "",
            },
        )

    # ------------------------------------------------------------------
    # Internal checkers
    # ------------------------------------------------------------------

    async def _check_overdue(
        self,
        med: dict[str, Any],
        state: dict[str, Any],
        notif_config: dict[str, Any],
        overrides: dict[str, Any],
    ) -> None:
        if not state.get("is_overdue"):
            return

        enabled = overrides.get(
            CONF_NOTIF_OVERRIDE_OVERDUE,
            notif_config.get(CONF_NOTIF_OVERDUE_ENABLED, False),
        )
        if not enabled:
            return

        overdue_since = state.get("overdue_since", "")
        fire_key = f"{med['id']}_overdue_{overdue_since}"
        if fire_key in self._fired:
            return

        delay = notif_config.get(CONF_NOTIF_OVERDUE_DELAY, DEFAULT_OVERDUE_DELAY)
        if delay and delay > 0:
            # Check if enough time has passed since overdue_since
            if overdue_since:
                from datetime import datetime
                try:
                    overdue_dt = datetime.fromisoformat(overdue_since)
                    from homeassistant.util.dt import now as ha_now
                    elapsed = (ha_now() - overdue_dt).total_seconds() / 60
                    if elapsed < delay:
                        return
                except ValueError:
                    pass

        title = notif_config.get(CONF_NOTIF_OVERDUE_TITLE, DEFAULT_OVERDUE_TITLE)
        message = notif_config.get(CONF_NOTIF_OVERDUE_MESSAGE, DEFAULT_OVERDUE_MESSAGE)
        await self._send(
            notif_config,
            title,
            message,
            {
                "medication": med["name"],
                "dose": med.get("dose", ""),
                "time": state.get("next_dose_time", ""),
                "overdue_since": _format_time(overdue_since),
            },
        )
        self._fired.add(fire_key)

    async def _check_due_soon(
        self,
        med: dict[str, Any],
        state: dict[str, Any],
        notif_config: dict[str, Any],
        overrides: dict[str, Any],
    ) -> None:
        if not state.get("is_due_soon"):
            return

        enabled = overrides.get(
            CONF_NOTIF_OVERRIDE_DUE_SOON,
            notif_config.get(CONF_NOTIF_DUE_SOON_ENABLED, False),
        )
        if not enabled:
            return

        next_dose_time = state.get("next_dose_time", "")
        fire_key = f"{med['id']}_due_soon_{next_dose_time}"
        if fire_key in self._fired:
            return

        title = notif_config.get(CONF_NOTIF_DUE_SOON_TITLE, DEFAULT_DUE_SOON_TITLE)
        message = notif_config.get(CONF_NOTIF_DUE_SOON_MESSAGE, DEFAULT_DUE_SOON_MESSAGE)
        await self._send(
            notif_config,
            title,
            message,
            {
                "medication": med["name"],
                "dose": med.get("dose", ""),
                "time": next_dose_time,
                "overdue_since": "",
            },
        )
        self._fired.add(fire_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send(
        self,
        notif_config: dict[str, Any],
        title_template: str,
        message_template: str,
        placeholders: dict[str, str],
    ) -> None:
        """Render templates and call the notify service."""
        target = notif_config.get(CONF_NOTIF_TARGET, DEFAULT_NOTIFY_TARGET)
        # target is e.g. "notify.persistent_notification" or "notify.mobile_app_phone"
        parts = target.split(".", 1)
        if len(parts) != 2:
            _LOGGER.warning("Invalid notify target: %s", target)
            return

        domain, service = parts[0], parts[1]
        title = _render(title_template, placeholders)
        message = _render(message_template, placeholders)

        try:
            await self._hass.services.async_call(
                domain,
                service,
                {"title": title, "message": message},
                blocking=False,
            )
        except Exception as err:
            _LOGGER.error("Failed to send notification via %s: %s", target, err)

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._fired_date:
            self._fired.clear()
            self._fired_date = today


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _render(template: str, placeholders: dict[str, str]) -> str:
    """Safely render a template string with placeholders."""
    try:
        return template.format(**placeholders)
    except (KeyError, ValueError):
        return template


def _format_time(iso_str: str) -> str:
    """Extract HH:MM from an ISO datetime string for display."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_str
