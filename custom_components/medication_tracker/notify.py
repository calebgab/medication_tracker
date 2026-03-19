"""Notification engine for Medication Tracker."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later

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

# Action identifiers sent to/from the mobile app
ACTION_MARK_TAKEN = "MT_MARK_TAKEN"
ACTION_REMIND_5MIN = "MT_REMIND_5MIN"


def _is_ios(hass: HomeAssistant, target: str) -> bool:
    """Return True if the notify target belongs to an Apple device."""
    # target is e.g. "notify.mobile_app_johns_iphone"
    # The mobile_app device is registered with manufacturer "Apple" for iOS devices.
    if not target.startswith("notify.mobile_app_"):
        return False
    device_name = target.replace("notify.mobile_app_", "")
    registry = dr.async_get(hass)
    for device in registry.devices.values():
        if device.manufacturer and device.manufacturer.lower() == "apple":
            # Match by checking if any identifier contains the device name
            for _, identifier in device.identifiers:
                if device_name in identifier.lower():
                    return True
    return False


def _build_action_data(hass: HomeAssistant, target: str, med_id: str) -> dict[str, Any]:
    """Build platform-appropriate action data for an actionable notification."""
    actions = [
        {"action": ACTION_MARK_TAKEN, "title": "Mark taken"},
        {"action": ACTION_REMIND_5MIN, "title": "Remind in 5 min"},
    ]
    if _is_ios(hass, target):
        return {
            "push": {
                "category": "MEDICATION_ALERT",
            },
            "actions": actions,
            "tag": f"medication_{med_id}",
        }
    # Android
    return {
        "actions": actions,
        "tag": f"medication_{med_id}",
        "persistent": False,
    }


class MedicationNotifier:
    """Fires HA notifications based on medication state changes."""

    def __init__(self, hass: HomeAssistant, coordinator: MedicationCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        # Tracks which notifications have already fired today to prevent repeats.
        self._fired: set[str] = set()
        self._fired_date: date = date.today()
        # Unsubscribe handle for the mobile_app_notification_action listener
        self._unsub_action: Any = None
        self._register_action_listener()

    # ------------------------------------------------------------------
    # Action listener
    # ------------------------------------------------------------------

    def _register_action_listener(self) -> None:
        """Listen for actionable notification responses from the mobile app."""
        @callback
        def _handle_action(event: Any) -> None:
            action = event.data.get("action", "")
            if action not in (ACTION_MARK_TAKEN, ACTION_REMIND_5MIN):
                return

            # The tag we set was "medication_{med_id}"
            tag = event.data.get("tag", "")
            if not tag.startswith("medication_"):
                return
            med_id = tag.replace("medication_", "", 1)

            if action == ACTION_MARK_TAKEN:
                self._hass.async_create_task(
                    self._coordinator.async_mark_taken(med_id)
                )
            elif action == ACTION_REMIND_5MIN:
                self._schedule_reminder(med_id)

        self._unsub_action = self._hass.bus.async_listen(
            "mobile_app_notification_action", _handle_action
        )

    def _schedule_reminder(self, med_id: str) -> None:
        """Fire a reminder notification for med_id after 5 minutes."""
        @callback
        def _send_reminder(_now: Any) -> None:
            med = self._coordinator.get_medication(med_id)
            if not med:
                return
            notif_config = self._coordinator.notification_config
            state = self._coordinator.get_med_state(med_id)
            title = notif_config.get(CONF_NOTIF_OVERDUE_TITLE, DEFAULT_OVERDUE_TITLE)
            message = notif_config.get(CONF_NOTIF_OVERDUE_MESSAGE, DEFAULT_OVERDUE_MESSAGE)
            self._hass.async_create_task(
                self._send(
                    notif_config,
                    title,
                    message,
                    {
                        "medication": med["name"],
                        "dose": med.get("dose", ""),
                        "time": state.get("next_dose_time", ""),
                        "overdue_since": _format_time(state.get("overdue_since", "")),
                    },
                    med_id=med_id,
                    actionable=True,
                )
            )

        async_call_later(self._hass, 300, _send_reminder)

    def unsubscribe(self) -> None:
        """Clean up the event listener on unload."""
        if self._unsub_action is not None:
            self._unsub_action()
            self._unsub_action = None

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
            med_id=med_id,
            actionable=False,
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
            if overdue_since:
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
            med_id=med["id"],
            actionable=True,
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
            med_id=med["id"],
            actionable=True,
        )
        self._fired.add(fire_key)

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def _send(
        self,
        notif_config: dict[str, Any],
        title_template: str,
        message_template: str,
        placeholders: dict[str, str],
        med_id: str = "",
        actionable: bool = False,
    ) -> None:
        """Render templates and call the notify service."""
        target = notif_config.get(CONF_NOTIF_TARGET, DEFAULT_NOTIFY_TARGET)
        parts = target.split(".", 1)
        if len(parts) != 2:
            _LOGGER.warning("Invalid notify target: %s", target)
            return

        domain, service = parts[0], parts[1]
        title = _render(title_template, placeholders)
        message = _render(message_template, placeholders)

        service_data: dict[str, Any] = {"title": title, "message": message}

        if actionable and med_id and target != DEFAULT_NOTIFY_TARGET:
            service_data["data"] = _build_action_data(self._hass, target, med_id)

        try:
            await self._hass.services.async_call(
                domain,
                service,
                service_data,
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
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_str
