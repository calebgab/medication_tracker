"""DataUpdateCoordinator for Medication Tracker."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    OVERDUE_GRACE_MINUTES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# How often the coordinator refreshes internal state (no external API, just recalculates)
UPDATE_INTERVAL = timedelta(minutes=1)


class MedicationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage medication state and persistence."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry_id = entry_id
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._medications: list[dict[str, Any]] = []
        # Keyed by medication_id -> list of log entries for today
        self._dose_log: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load persisted data from storage."""
        stored = await self._store.async_load()
        if stored:
            self._medications = stored.get("medications", [])
            raw_log = stored.get("dose_log", {})
            today_str = date.today().isoformat()
            # Only keep today's log entries to avoid unbounded growth
            self._dose_log = {
                med_id: [e for e in entries if e.get("date") == today_str]
                for med_id, entries in raw_log.items()
            }
        else:
            self._medications = []
            self._dose_log = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Recalculate derived state for all medications."""
        now = dt_util.now()
        result: dict[str, Any] = {}
        for med in self._medications:
            result[med["id"]] = self._build_med_state(med, now)
        return result

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def medications(self) -> list[dict[str, Any]]:
        """Return the list of configured medications."""
        return list(self._medications)

    def get_medication(self, med_id: str) -> dict[str, Any] | None:
        """Return a single medication config by id."""
        return next((m for m in self._medications if m["id"] == med_id), None)

    def get_med_state(self, med_id: str) -> dict[str, Any]:
        """Return current derived state for a medication."""
        if self.data and med_id in self.data:
            return self.data[med_id]
        med = self.get_medication(med_id)
        if med:
            return self._build_med_state(med, dt_util.now())
        return {}

    # ------------------------------------------------------------------
    # Medication CRUD
    # ------------------------------------------------------------------

    async def async_add_medication(self, config: dict[str, Any]) -> str:
        """Add a new medication. Returns its generated id."""
        med_id = str(uuid.uuid4())
        entry = {
            "id": med_id,
            "name": config["name"],
            "dose": config.get("dose", ""),
            "times": config.get("times", []),
            "days": config.get("days", []),
            "notes": config.get("notes", ""),
        }
        self._medications.append(entry)
        await self._async_save()
        await self.async_refresh()
        return med_id

    async def async_update_medication(self, med_id: str, config: dict[str, Any]) -> bool:
        """Update an existing medication. Returns True if found."""
        for i, med in enumerate(self._medications):
            if med["id"] == med_id:
                self._medications[i] = {
                    "id": med_id,
                    "name": config.get("name", med["name"]),
                    "dose": config.get("dose", med["dose"]),
                    "times": config.get("times", med["times"]),
                    "days": config.get("days", med["days"]),
                    "notes": config.get("notes", med["notes"]),
                }
                await self._async_save()
                await self.async_refresh()
                return True
        return False

    async def async_remove_medication(self, med_id: str) -> bool:
        """Remove a medication. Returns True if found."""
        before = len(self._medications)
        self._medications = [m for m in self._medications if m["id"] != med_id]
        if len(self._medications) < before:
            self._dose_log.pop(med_id, None)
            await self._async_save()
            await self.async_refresh()
            return True
        return False

    # ------------------------------------------------------------------
    # Dose logging
    # ------------------------------------------------------------------

    async def async_mark_taken(
        self,
        med_id: str,
        taken_at: datetime | None = None,
        scheduled_time: str | None = None,
    ) -> bool:
        """Log that a dose was taken. Returns True if medication exists."""
        if not self.get_medication(med_id):
            return False
        now = taken_at or dt_util.now()
        entry = {
            "date": date.today().isoformat(),
            "taken_at": now.isoformat(),
            "scheduled_time": scheduled_time,
            "action": "taken",
        }
        self._dose_log.setdefault(med_id, []).append(entry)
        await self._async_save()
        await self.async_refresh()
        return True

    async def async_mark_skipped(
        self,
        med_id: str,
        scheduled_time: str | None = None,
    ) -> bool:
        """Log that a dose was intentionally skipped."""
        if not self.get_medication(med_id):
            return False
        entry = {
            "date": date.today().isoformat(),
            "taken_at": None,
            "scheduled_time": scheduled_time,
            "action": "skipped",
        }
        self._dose_log.setdefault(med_id, []).append(entry)
        await self._async_save()
        await self.async_refresh()
        return True

    async def async_reset_today(self, med_id: str) -> bool:
        """Clear all of today's log entries for a medication."""
        if not self.get_medication(med_id):
            return False
        today = date.today().isoformat()
        self._dose_log[med_id] = [
            e for e in self._dose_log.get(med_id, []) if e.get("date") != today
        ]
        await self._async_save()
        await self.async_refresh()
        return True

    # ------------------------------------------------------------------
    # Internal state calculation
    # ------------------------------------------------------------------

    def _build_med_state(self, med: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Derive all sensor-relevant state for a medication."""
        today = now.date()
        today_str = today.isoformat()
        scheduled_times: list[str] = med.get("times", [])
        days: list[int] = med.get("days", [])

        # Is today a scheduled day?
        scheduled_today = not days or (now.weekday() in days)

        # Today's log entries
        today_entries = [
            e for e in self._dose_log.get(med["id"], []) if e.get("date") == today_str
        ]
        taken_entries = [e for e in today_entries if e.get("action") == "taken"]
        skipped_entries = [e for e in today_entries if e.get("action") == "skipped"]

        # Determine next scheduled dose time
        next_dose_dt: datetime | None = None
        next_dose_time_str: str | None = None
        for t_str in sorted(scheduled_times):
            try:
                t = time.fromisoformat(t_str)
            except ValueError:
                continue
            candidate = datetime.combine(today, t, tzinfo=now.tzinfo)
            if candidate > now:
                next_dose_dt = candidate
                next_dose_time_str = t_str
                break
        # If no more times today, find the next scheduled day
        if next_dose_dt is None and scheduled_times:
            for days_ahead in range(1, 8):
                future_date = today + timedelta(days=days_ahead)
                if not days or (future_date.weekday() in days):
                    t_str = sorted(scheduled_times)[0]
                    try:
                        t = time.fromisoformat(t_str)
                        next_dose_dt = datetime.combine(future_date, t, tzinfo=now.tzinfo)
                        next_dose_time_str = t_str
                    except ValueError:
                        pass
                    break

        # Overdue: any scheduled time today that is > grace period in the past with no taken/skipped entry
        is_overdue = False
        overdue_since: str | None = None
        if scheduled_today:
            for t_str in sorted(scheduled_times):
                try:
                    t = time.fromisoformat(t_str)
                except ValueError:
                    continue
                scheduled_dt = datetime.combine(today, t, tzinfo=now.tzinfo)
                grace_dt = scheduled_dt + timedelta(minutes=OVERDUE_GRACE_MINUTES)
                if now > grace_dt:
                    # Check if this slot was handled
                    handled = any(e.get("scheduled_time") == t_str for e in today_entries)
                    if not handled:
                        is_overdue = True
                        overdue_since = scheduled_dt.isoformat()
                        break  # Report earliest unhandled overdue slot

        # Due soon: within DUE_SOON_MINUTES of next dose
        is_due_soon = False
        if next_dose_dt is not None:
            minutes_until = (next_dose_dt - now).total_seconds() / 60
            is_due_soon = 0 <= minutes_until <= 60

        # Last taken timestamp
        last_taken: str | None = None
        if taken_entries:
            last_taken = max(
                (e["taken_at"] for e in taken_entries if e.get("taken_at")),
                default=None,
            )

        # Streak: consecutive days with at least one "taken" entry
        streak = self._calculate_streak(med["id"], today)

        return {
            "name": med["name"],
            "dose": med.get("dose", ""),
            "times": scheduled_times,
            "days": days,
            "notes": med.get("notes", ""),
            "scheduled_today": scheduled_today,
            "taken_today": len(taken_entries),
            "skipped_today": len(skipped_entries),
            "doses_scheduled_today": len(scheduled_times) if scheduled_today else 0,
            "is_overdue": is_overdue,
            "overdue_since": overdue_since,
            "is_due_soon": is_due_soon,
            "next_dose": next_dose_dt.isoformat() if next_dose_dt else None,
            "next_dose_time": next_dose_time_str,
            "last_taken": last_taken,
            "streak": streak,
        }

    def _calculate_streak(self, med_id: str, today: date) -> int:
        """Count consecutive days with at least one taken dose, ending today."""
        # Build a set of dates that have taken entries
        all_entries = self._dose_log.get(med_id, [])
        taken_dates: set[str] = {e["date"] for e in all_entries if e.get("action") == "taken"}
        streak = 0
        check_date = today
        while check_date.isoformat() in taken_dates:
            streak += 1
            check_date -= timedelta(days=1)
        return streak

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _async_save(self) -> None:
        """Persist medications and dose log to storage."""
        await self._store.async_save(
            {
                "medications": self._medications,
                "dose_log": self._dose_log,
            }
        )
