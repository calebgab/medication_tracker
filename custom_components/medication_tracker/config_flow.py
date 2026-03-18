"""Config flow for Medication Tracker."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_MED_DAYS,
    CONF_MED_DOSE,
    CONF_MED_NAME,
    CONF_MED_NOTES,
    CONF_MED_TIMES,
    CONF_MEDICATIONS,
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
    DOMAIN,
)

_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def _validate_times(times_raw: str) -> list[str]:
    """Parse and validate a comma-separated list of HH:MM times."""
    times = [t.strip() for t in times_raw.split(",") if t.strip()]
    for t in times:
        if not _TIME_PATTERN.match(t):
            raise vol.Invalid(f"Invalid time format: '{t}'. Use HH:MM.")
    return times


def _validate_days(days_raw: str) -> list[int]:
    """Parse a comma-separated list of day abbreviations or ints (0=Mon..6=Sun)."""
    if not days_raw.strip():
        return []
    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    result: list[int] = []
    for part in days_raw.split(","):
        part = part.strip().lower()
        if part in day_map:
            result.append(day_map[part])
        elif part.isdigit() and 0 <= int(part) <= 6:
            result.append(int(part))
        else:
            raise vol.Invalid(
                f"Invalid day '{part}'. Use mon/tue/wed/thu/fri/sat/sun or 0-6."
            )
    return sorted(set(result))


def _get_notify_services(hass: Any) -> dict[str, str]:
    """Return a dict of {service_id: label} for all notify.mobile_app_* services."""
    services: dict[str, str] = {}
    all_services = hass.services.async_services()
    notify_services = all_services.get("notify", {})
    for service_name in sorted(notify_services):
        if service_name.startswith("mobile_app_"):
            full_name = f"notify.{service_name}"
            # Make a friendlier label by stripping the prefix and replacing underscores
            label = service_name.replace("mobile_app_", "").replace("_", " ").title()
            services[full_name] = label
    # Always include persistent_notification as a fallback option
    services[DEFAULT_NOTIFY_TARGET] = "Persistent notification (HA bell)"
    return services


class MedicationTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            title = user_input.get("title", "Medication Tracker").strip() or "Medication Tracker"
            await self.async_set_unique_id(title.lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=title,
                data={CONF_MEDICATIONS: []},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("title", default="Medication Tracker"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MedicationOptionsFlow:
        return MedicationOptionsFlow(config_entry)


class MedicationOptionsFlow(OptionsFlow):
    """Options flow: medications + notifications."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._edit_id: str | None = None
        self._override_med_id: str | None = None

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        meds = coordinator.medications

        if user_input is not None:
            action = user_input.get("action", "done")
            if action == "add":
                return await self.async_step_add_medication()
            if action == "remove":
                return await self.async_step_remove_medication()
            if action == "notifications":
                return await self.async_step_notifications()
            if action.startswith("edit:"):
                self._edit_id = action.split(":", 1)[1]
                return await self.async_step_edit_medication()
            return self.async_create_entry(title="", data={})

        action_options: list[str] = ["add"]
        for med in meds:
            action_options.append(f"edit:{med['id']}")
        action_options += ["remove", "notifications", "done"]

        action_labels: dict[str, str] = {
            "add": "Add new medication",
            "notifications": "Notifications",
            "done": "Done",
        }
        for med in meds:
            action_labels[f"edit:{med['id']}"] = f"Edit: {med['name']}"
        action_labels["remove"] = "Remove a medication"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="done"): vol.In(action_labels),
                }
            ),
            description_placeholders={"count": str(len(meds))},
        )

    # ------------------------------------------------------------------
    # Medication: add
    # ------------------------------------------------------------------

    async def async_step_add_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                times = _validate_times(user_input.get(CONF_MED_TIMES, ""))
            except vol.Invalid:
                errors[CONF_MED_TIMES] = "invalid_time_format"
                times = []

            try:
                days = _validate_days(user_input.get(CONF_MED_DAYS, ""))
            except vol.Invalid:
                errors[CONF_MED_DAYS] = "invalid_day_format"
                days = []

            if not errors:
                coordinator = self._entry.runtime_data
                await coordinator.async_add_medication(
                    {
                        "name": user_input[CONF_MED_NAME],
                        "dose": user_input.get(CONF_MED_DOSE, ""),
                        "times": times,
                        "days": days,
                        "notes": user_input.get(CONF_MED_NOTES, ""),
                    }
                )
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_medication",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MED_NAME): str,
                    vol.Optional(CONF_MED_DOSE, default=""): str,
                    vol.Optional(CONF_MED_TIMES, default=""): str,
                    vol.Optional(CONF_MED_DAYS, default=""): str,
                    vol.Optional(CONF_MED_NOTES, default=""): str,
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Medication: edit
    # ------------------------------------------------------------------

    async def async_step_edit_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        coordinator = self._entry.runtime_data
        med = coordinator.get_medication(self._edit_id or "")

        if med is None:
            return await self.async_step_init()

        if user_input is not None:
            try:
                times = _validate_times(user_input.get(CONF_MED_TIMES, ""))
            except vol.Invalid:
                errors[CONF_MED_TIMES] = "invalid_time_format"
                times = []

            try:
                days = _validate_days(user_input.get(CONF_MED_DAYS, ""))
            except vol.Invalid:
                errors[CONF_MED_DAYS] = "invalid_day_format"
                days = []

            if not errors:
                await coordinator.async_update_medication(
                    self._edit_id,  # type: ignore[arg-type]
                    {
                        "name": user_input[CONF_MED_NAME],
                        "dose": user_input.get(CONF_MED_DOSE, ""),
                        "times": times,
                        "days": days,
                        "notes": user_input.get(CONF_MED_NOTES, ""),
                    },
                )
                return await self.async_step_init()

        times_str = ", ".join(med.get("times", []))
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        days_str = ", ".join(day_names[d] for d in med.get("days", []))

        return self.async_show_form(
            step_id="edit_medication",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MED_NAME, default=med["name"]): str,
                    vol.Optional(CONF_MED_DOSE, default=med.get("dose", "")): str,
                    vol.Optional(CONF_MED_TIMES, default=times_str): str,
                    vol.Optional(CONF_MED_DAYS, default=days_str): str,
                    vol.Optional(CONF_MED_NOTES, default=med.get("notes", "")): str,
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Medication: remove
    # ------------------------------------------------------------------

    async def async_step_remove_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        meds = coordinator.medications

        if not meds:
            return await self.async_step_init()

        if user_input is not None:
            med_id = user_input.get("medication_id")
            if med_id:
                await coordinator.async_remove_medication(med_id)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove_medication",
            data_schema=vol.Schema(
                {
                    vol.Required("medication_id"): vol.In(
                        {m["id"]: m["name"] for m in meds}
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: global settings
    # ------------------------------------------------------------------

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        cfg = coordinator.notification_config
        notify_services = _get_notify_services(self.hass)

        if user_input is not None:
            action = user_input.get("action", "save")

            if action == "edit_overdue_message":
                await coordinator.async_update_notification_config(
                    _notification_config_from_input(user_input, cfg)
                )
                return await self.async_step_notification_overdue_message()

            if action == "edit_due_soon_message":
                await coordinator.async_update_notification_config(
                    _notification_config_from_input(user_input, cfg)
                )
                return await self.async_step_notification_due_soon_message()

            if action == "edit_taken_message":
                await coordinator.async_update_notification_config(
                    _notification_config_from_input(user_input, cfg)
                )
                return await self.async_step_notification_taken_message()

            if action == "per_medication":
                await coordinator.async_update_notification_config(
                    _notification_config_from_input(user_input, cfg)
                )
                return await self.async_step_notification_per_medication()

            await coordinator.async_update_notification_config(
                _notification_config_from_input(user_input, cfg)
            )
            return await self.async_step_init()

        # Current target — ensure it's in the list even if services changed
        current_target = cfg.get(CONF_NOTIF_TARGET, DEFAULT_NOTIFY_TARGET)
        if current_target not in notify_services:
            notify_services[current_target] = current_target

        action_labels = {
            "save": "Save and go back",
            "edit_overdue_message": "Edit overdue message template",
            "edit_due_soon_message": "Edit due soon message template",
            "edit_taken_message": "Edit taken confirmation message",
            "per_medication": "Per-medication overrides",
        }

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIF_TARGET,
                        default=current_target,
                    ): vol.In(notify_services),
                    vol.Optional(
                        CONF_NOTIF_OVERDUE_ENABLED,
                        default=cfg.get(CONF_NOTIF_OVERDUE_ENABLED, False),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIF_OVERDUE_DELAY,
                        default=cfg.get(CONF_NOTIF_OVERDUE_DELAY, DEFAULT_OVERDUE_DELAY),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
                    vol.Optional(
                        CONF_NOTIF_DUE_SOON_ENABLED,
                        default=cfg.get(CONF_NOTIF_DUE_SOON_ENABLED, False),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIF_TAKEN_ENABLED,
                        default=cfg.get(CONF_NOTIF_TAKEN_ENABLED, False),
                    ): bool,
                    vol.Required("action", default="save"): vol.In(action_labels),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: overdue message template
    # ------------------------------------------------------------------

    async def async_step_notification_overdue_message(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        cfg = coordinator.notification_config

        if user_input is not None:
            updated = {
                **cfg,
                CONF_NOTIF_OVERDUE_TITLE: user_input.get(
                    CONF_NOTIF_OVERDUE_TITLE, DEFAULT_OVERDUE_TITLE
                ),
                CONF_NOTIF_OVERDUE_MESSAGE: user_input.get(
                    CONF_NOTIF_OVERDUE_MESSAGE, DEFAULT_OVERDUE_MESSAGE
                ),
            }
            await coordinator.async_update_notification_config(updated)
            return await self.async_step_notifications()

        return self.async_show_form(
            step_id="notification_overdue_message",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIF_OVERDUE_TITLE,
                        default=cfg.get(CONF_NOTIF_OVERDUE_TITLE, DEFAULT_OVERDUE_TITLE),
                    ): str,
                    vol.Optional(
                        CONF_NOTIF_OVERDUE_MESSAGE,
                        default=cfg.get(CONF_NOTIF_OVERDUE_MESSAGE, DEFAULT_OVERDUE_MESSAGE),
                    ): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: due soon message template
    # ------------------------------------------------------------------

    async def async_step_notification_due_soon_message(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        cfg = coordinator.notification_config

        if user_input is not None:
            updated = {
                **cfg,
                CONF_NOTIF_DUE_SOON_TITLE: user_input.get(
                    CONF_NOTIF_DUE_SOON_TITLE, DEFAULT_DUE_SOON_TITLE
                ),
                CONF_NOTIF_DUE_SOON_MESSAGE: user_input.get(
                    CONF_NOTIF_DUE_SOON_MESSAGE, DEFAULT_DUE_SOON_MESSAGE
                ),
            }
            await coordinator.async_update_notification_config(updated)
            return await self.async_step_notifications()

        return self.async_show_form(
            step_id="notification_due_soon_message",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIF_DUE_SOON_TITLE,
                        default=cfg.get(CONF_NOTIF_DUE_SOON_TITLE, DEFAULT_DUE_SOON_TITLE),
                    ): str,
                    vol.Optional(
                        CONF_NOTIF_DUE_SOON_MESSAGE,
                        default=cfg.get(CONF_NOTIF_DUE_SOON_MESSAGE, DEFAULT_DUE_SOON_MESSAGE),
                    ): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: taken confirmation message template
    # ------------------------------------------------------------------

    async def async_step_notification_taken_message(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        cfg = coordinator.notification_config

        if user_input is not None:
            updated = {
                **cfg,
                CONF_NOTIF_TAKEN_TITLE: user_input.get(
                    CONF_NOTIF_TAKEN_TITLE, DEFAULT_TAKEN_TITLE
                ),
                CONF_NOTIF_TAKEN_MESSAGE: user_input.get(
                    CONF_NOTIF_TAKEN_MESSAGE, DEFAULT_TAKEN_MESSAGE
                ),
            }
            await coordinator.async_update_notification_config(updated)
            return await self.async_step_notifications()

        return self.async_show_form(
            step_id="notification_taken_message",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIF_TAKEN_TITLE,
                        default=cfg.get(CONF_NOTIF_TAKEN_TITLE, DEFAULT_TAKEN_TITLE),
                    ): str,
                    vol.Optional(
                        CONF_NOTIF_TAKEN_MESSAGE,
                        default=cfg.get(CONF_NOTIF_TAKEN_MESSAGE, DEFAULT_TAKEN_MESSAGE),
                    ): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: pick medication for per-medication overrides
    # ------------------------------------------------------------------

    async def async_step_notification_per_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        meds = coordinator.medications

        if not meds:
            return await self.async_step_notifications()

        if user_input is not None:
            self._override_med_id = user_input.get("medication_id")
            return await self.async_step_notification_med_overrides()

        return self.async_show_form(
            step_id="notification_per_medication",
            data_schema=vol.Schema(
                {
                    vol.Required("medication_id"): vol.In(
                        {m["id"]: m["name"] for m in meds}
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Notifications: per-medication override toggles
    # ------------------------------------------------------------------

    async def async_step_notification_med_overrides(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self._entry.runtime_data
        med = coordinator.get_medication(self._override_med_id or "")

        if med is None:
            return await self.async_step_notifications()

        existing = med.get(CONF_NOTIF_OVERRIDES, {})
        cfg = coordinator.notification_config

        if user_input is not None:
            overrides: dict[str, Any] = {}
            global_overdue = cfg.get(CONF_NOTIF_OVERDUE_ENABLED, False)
            global_due_soon = cfg.get(CONF_NOTIF_DUE_SOON_ENABLED, False)
            global_taken = cfg.get(CONF_NOTIF_TAKEN_ENABLED, False)

            val_overdue = user_input.get(CONF_NOTIF_OVERRIDE_OVERDUE)
            val_due_soon = user_input.get(CONF_NOTIF_OVERRIDE_DUE_SOON)
            val_taken = user_input.get(CONF_NOTIF_OVERRIDE_TAKEN)

            if val_overdue is not None and val_overdue != global_overdue:
                overrides[CONF_NOTIF_OVERRIDE_OVERDUE] = val_overdue
            if val_due_soon is not None and val_due_soon != global_due_soon:
                overrides[CONF_NOTIF_OVERRIDE_DUE_SOON] = val_due_soon
            if val_taken is not None and val_taken != global_taken:
                overrides[CONF_NOTIF_OVERRIDE_TAKEN] = val_taken

            await coordinator.async_update_med_notification_overrides(
                self._override_med_id,  # type: ignore[arg-type]
                overrides,
            )
            return await self.async_step_notifications()

        global_overdue = cfg.get(CONF_NOTIF_OVERDUE_ENABLED, False)
        global_due_soon = cfg.get(CONF_NOTIF_DUE_SOON_ENABLED, False)
        global_taken = cfg.get(CONF_NOTIF_TAKEN_ENABLED, False)

        return self.async_show_form(
            step_id="notification_med_overrides",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIF_OVERRIDE_OVERDUE,
                        default=existing.get(CONF_NOTIF_OVERRIDE_OVERDUE, global_overdue),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIF_OVERRIDE_DUE_SOON,
                        default=existing.get(CONF_NOTIF_OVERRIDE_DUE_SOON, global_due_soon),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIF_OVERRIDE_TAKEN,
                        default=existing.get(CONF_NOTIF_OVERRIDE_TAKEN, global_taken),
                    ): bool,
                }
            ),
            description_placeholders={"medication": med["name"]},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _notification_config_from_input(
    user_input: dict[str, Any], existing: dict[str, Any]
) -> dict[str, Any]:
    """Build a notification config dict from options flow form input."""
    return {
        **existing,
        CONF_NOTIF_TARGET: user_input.get(
            CONF_NOTIF_TARGET, existing.get(CONF_NOTIF_TARGET, DEFAULT_NOTIFY_TARGET)
        ),
        CONF_NOTIF_OVERDUE_ENABLED: user_input.get(
            CONF_NOTIF_OVERDUE_ENABLED, existing.get(CONF_NOTIF_OVERDUE_ENABLED, False)
        ),
        CONF_NOTIF_OVERDUE_DELAY: user_input.get(
            CONF_NOTIF_OVERDUE_DELAY,
            existing.get(CONF_NOTIF_OVERDUE_DELAY, DEFAULT_OVERDUE_DELAY),
        ),
        CONF_NOTIF_DUE_SOON_ENABLED: user_input.get(
            CONF_NOTIF_DUE_SOON_ENABLED, existing.get(CONF_NOTIF_DUE_SOON_ENABLED, False)
        ),
        CONF_NOTIF_TAKEN_ENABLED: user_input.get(
            CONF_NOTIF_TAKEN_ENABLED, existing.get(CONF_NOTIF_TAKEN_ENABLED, False)
        ),
    }
