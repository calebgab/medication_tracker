"""Config flow for Medication Tracker."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MED_DAYS,
    CONF_MED_DOSE,
    CONF_MED_NAME,
    CONF_MED_NOTES,
    CONF_MED_TIMES,
    CONF_MEDICATIONS,
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


class MedicationTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow — just creates the entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an optional label for this tracker instance."""
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
        """Return the options flow handler."""
        return MedicationOptionsFlow(config_entry)


class MedicationOptionsFlow(OptionsFlow):
    """Options flow: add / edit / remove medications."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise."""
        self._entry = config_entry
        self._action: str | None = None
        self._edit_id: str | None = None

    # ------------------------------------------------------------------
    # Entry point: pick action
    # ------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present the menu: add / edit / remove / done."""
        coordinator = self._entry.runtime_data
        meds = coordinator.medications

        if user_input is not None:
            action = user_input.get("action", "done")
            if action == "add":
                return await self.async_step_add_medication()
            if action == "remove":
                return await self.async_step_remove_medication()
            if action.startswith("edit:"):
                self._edit_id = action.split(":", 1)[1]
                return await self.async_step_edit_medication()
            # done
            return self.async_create_entry(title="", data={})

        action_options: list[str] = ["add"]
        for med in meds:
            action_options.append(f"edit:{med['id']}")
        action_options += ["remove", "done"]

        action_labels: dict[str, str] = {"add": "➕ Add new medication", "done": "✅ Done"}
        for med in meds:
            action_labels[f"edit:{med['id']}"] = f"✏️ Edit: {med['name']}"
        action_labels["remove"] = "🗑️ Remove a medication"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="done"): vol.In(action_labels),
                }
            ),
            description_placeholders={
                "count": str(len(meds)),
            },
        )

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    async def async_step_add_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to add a new medication."""
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
    # Edit
    # ------------------------------------------------------------------

    async def async_step_edit_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to edit an existing medication."""
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
    # Remove
    # ------------------------------------------------------------------

    async def async_step_remove_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a medication to remove."""
        coordinator = self._entry.runtime_data
        meds = coordinator.medications

        if not meds:
            return await self.async_step_init()

        if user_input is not None:
            med_id = user_input.get("medication_id")
            if med_id:
                await coordinator.async_remove_medication(med_id)
            return await self.async_step_init()

        choices: dict[str, str] = {m["id"]: m["name"] for m in meds}

        return self.async_show_form(
            step_id="remove_medication",
            data_schema=vol.Schema(
                {
                    vol.Required("medication_id"): vol.In(choices),
                }
            ),
        )
