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
    CONF_NOTIFICATIONS,
    CONF_PRN_MAX_PER_24H,
    CONF_PRN_MAX_PER_DAY,
    CONF_PRN_MIN_HOURS,
    DEFAULT_PRN_MAX_PER_24H,
    DEFAULT_PRN_MAX_PER_DAY,
    DEFAULT_PRN_MIN_HOURS,
    DOMAIN,
    MED_TYPE_PRN,
    MED_TYPE_SCHEDULED,
    OVERDUE_GRACE_MINUTES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=1)


class MedicationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage medication state and persistence."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry_id = entry_id
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._medications: list[dict[str, Any]] = []
        self._dose_log: dict[str, list[dict[str, Any]]] = {}
        self._notification_config: dict[str, Any] = {}
        # Notifier is set by __init__.py after construction
        self._notifier: Any = None

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
            self._dose_log = {
                med_id: [e for e in entries if e.get("date") == today_str]
                for med_id, entries in raw_log.items()
            }
            self._notification_config = stored.get(CONF_NOTIFICATIONS, {})
        else:
            self._medications = []
            self._dose_log = {}
            self._notification_config = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Recalculate derived state for all medications, then check notifications."""
        now = dt_util.now()
        result: dict[str, Any] = {}
        for med in self._medications:
            result[med["id"]] = self._build_med_state(med, now)

        if self._notifier is not None:
            try:
                await self._notifier.async_check_and_notify()
            except Exception as err:
                _LOGGER.error("Notification check failed: %s", err)

        return result

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def medications(self) -> list[dict[str, Any]]:
        return list(self._medications)

    @property
    def notification_config(self) -> dict[str, Any]:
        return dict(self._notification_config)

    def get_medication(self, med_id: str) -> dict[str, Any] | None:
        return next((m for m in self._medications if m["id"] == med_id), None)

    def get_med_state(self, med_id: str) -> dict[str, Any]:
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
        med_id = str(uuid.uuid4())
        entry = {
            "id": med_id,
            "name": config["name"],
            "dose": config.get("dose", ""),
            "med_type": config.get("med_type", MED_TYPE_SCHEDULED),
            "times": config.get("times", []),
            "days": config.get("days", []),
            "notes": config.get("notes", ""),
            "prn_max_per_day": config.get("prn_max_per_day", DEFAULT_PRN_MAX_PER_DAY),
            "prn_max_per_24h": config.get("prn_max_per_24h", DEFAULT_PRN_MAX_PER_24H),
            "prn_min_hours": config.get("prn_min_hours", DEFAULT_PRN_MIN_HOURS),
        }
        self._medications.append(entry)
        await self._async_save()
        await self.async_refresh()
        return med_id

    async def async_update_medication(self, med_id: str, config: dict[str, Any]) -> bool:
        for i, med in enumerate(self._medications):
            if med["id"] == med_id:
                self._medications[i] = {
                    "id": med_id,
                    "name": config.get("name", med["name"]),
                    "dose": config.get("dose", med["dose"]),
                    "med_type": config.get("med_type", med.get("med_type", MED_TYPE_SCHEDULED)),
                    "times": config.get("times", med["times"]),
                    "days": config.get("days", med["days"]),
                    "notes": config.get("notes", med["notes"]),
                    "prn_max_per_day": config.get("prn_max_per_day", med.get("prn_max_per_day", DEFAULT_PRN_MAX_PER_DAY)),
                    "prn_max_per_24h": config.get("prn_max_per_24h", med.get("prn_max_per_24h", DEFAULT_PRN_MAX_PER_24H)),
                    "prn_min_hours": config.get("prn_min_hours", med.get("prn_min_hours", DEFAULT_PRN_MIN_HOURS)),
                    # Preserve notification overrides
                    "notification_overrides": config.get(
                        "notification_overrides",
                        med.get("notification_overrides", {}),
                    ),
                }
                await self._async_save()
                await self.async_refresh()
                return True
        return False

    async def async_remove_medication(self, med_id: str) -> bool:
        before = len(self._medications)
        self._medications = [m for m in self._medications if m["id"] != med_id]
        if len(self._medications) < before:
            self._dose_log.pop(med_id, None)
            await self._async_save()
            await self.async_refresh()
            return True
        return False

    # ------------------------------------------------------------------
    # Notification config
    # ------------------------------------------------------------------

    async def async_update_notification_config(self, config: dict[str, Any]) -> None:
        """Persist global notification settings."""
        self._notification_config = config
        await self._async_save()

    async def async_update_med_notification_overrides(
        self, med_id: str, overrides: dict[str, Any]
    ) -> bool:
        """Persist per-medication notification overrides."""
        for i, med in enumerate(self._medications):
            if med["id"] == med_id:
                self._medications[i] = {**med, "notification_overrides": overrides}
                await self._async_save()
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

        if self._notifier is not None:
            try:
                await self._notifier.async_notify_taken(med_id)
            except Exception as err:
                _LOGGER.error("Taken notification failed: %s", err)

        return True

    async def async_mark_skipped(
        self,
        med_id: str,
        scheduled_time: str | None = None,
    ) -> bool:
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
        if med.get("med_type") == MED_TYPE_PRN:
            return self._build_prn_state(med, now)
        return self._build_scheduled_state(med, now)

    def _build_scheduled_state(self, med: dict[str, Any], now: datetime) -> dict[str, Any]:
        today = now.date()
        today_str = today.isoformat()
        scheduled_times: list[str] = med.get("times", [])
        days: list[int] = med.get("days", [])

        scheduled_today = not days or (now.weekday() in days)

        today_entries = [
            e for e in self._dose_log.get(med["id"], []) if e.get("date") == today_str
        ]
        taken_entries = [e for e in today_entries if e.get("action") == "taken"]
        skipped_entries = [e for e in today_entries if e.get("action") == "skipped"]

        next_dose_dt: datetime | None = None
        next_dose_time_str: str | None = None
        # Collect all slots already handled today (taken or skipped)
        handled_times: set[str] = {
            e["scheduled_time"]
            for e in today_entries
            if e.get("scheduled_time")
        }
        for t_str in sorted(scheduled_times):
            try:
                t = time.fromisoformat(t_str)
            except ValueError:
                continue
            candidate = datetime.combine(today, t, tzinfo=now.tzinfo)
            if candidate > now and t_str not in handled_times:
                next_dose_dt = candidate
                next_dose_time_str = t_str
                break

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
                    handled = any(e.get("scheduled_time") == t_str for e in today_entries)
                    if not handled:
                        is_overdue = True
                        overdue_since = scheduled_dt.isoformat()
                        break

        is_due_soon = False
        if next_dose_dt is not None:
            minutes_until = (next_dose_dt - now).total_seconds() / 60
            is_due_soon = 0 <= minutes_until <= 60

        last_taken: str | None = None
        if taken_entries:
            last_taken = max(
                (e["taken_at"] for e in taken_entries if e.get("taken_at")),
                default=None,
            )

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

    def _build_prn_state(self, med: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Derive state for a PRN (as-needed) medication."""
        today = now.date()
        today_str = today.isoformat()

        max_per_day: int = med.get("prn_max_per_day", DEFAULT_PRN_MAX_PER_DAY)
        max_per_24h: int = med.get("prn_max_per_24h", DEFAULT_PRN_MAX_PER_24H)
        min_hours: float = med.get("prn_min_hours", DEFAULT_PRN_MIN_HOURS)

        # All log entries (not just today) needed for 24h rolling window
        all_entries = self._dose_log.get(med["id"], [])
        taken_entries_all = [e for e in all_entries if e.get("action") == "taken" and e.get("taken_at")]

        # Today's taken entries
        today_entries = [e for e in all_entries if e.get("date") == today_str]
        taken_today = [e for e in today_entries if e.get("action") == "taken"]

        # 24h rolling window
        window_start = now - timedelta(hours=24)
        taken_24h = [
            e for e in taken_entries_all
            if e.get("taken_at") and datetime.fromisoformat(e["taken_at"]) >= window_start
        ]

        # Last taken
        last_taken: str | None = None
        last_taken_dt: datetime | None = None
        if taken_entries_all:
            last_taken = max(
                (e["taken_at"] for e in taken_entries_all if e.get("taken_at")),
                default=None,
            )
            if last_taken:
                last_taken_dt = datetime.fromisoformat(last_taken)

        # Determine availability
        is_available = True
        next_available_dt: datetime | None = None

        # Check daily max
        if len(taken_today) >= max_per_day:
            is_available = False
            # Not available again until tomorrow
            next_available_dt = None

        # Check 24h rolling max
        elif len(taken_24h) >= max_per_24h:
            is_available = False
            # Available when oldest dose in window falls out
            oldest_in_window = min(
                datetime.fromisoformat(e["taken_at"]) for e in taken_24h if e.get("taken_at")
            )
            next_available_dt = oldest_in_window + timedelta(hours=24)

        # Check min hours between doses
        elif last_taken_dt is not None:
            min_delta = timedelta(hours=min_hours)
            earliest_next = last_taken_dt + min_delta
            if now < earliest_next:
                is_available = False
                next_available_dt = earliest_next

        streak = self._calculate_streak(med["id"], today)

        return {
            "name": med["name"],
            "dose": med.get("dose", ""),
            "notes": med.get("notes", ""),
            "med_type": MED_TYPE_PRN,
            "prn_max_per_day": max_per_day,
            "prn_max_per_24h": max_per_24h,
            "prn_min_hours": min_hours,
            "is_available": is_available,
            "next_available": next_available_dt.isoformat() if next_available_dt else None,
            "doses_taken_today": len(taken_today),
            "doses_taken_24h": len(taken_24h),
            "last_taken": last_taken,
            "streak": streak,
            # Scheduled fields not applicable — set to safe defaults
            "times": [],
            "days": [],
            "scheduled_today": False,
            "taken_today": len(taken_today),
            "skipped_today": 0,
            "doses_scheduled_today": 0,
            "is_overdue": False,
            "overdue_since": None,
            "is_due_soon": False,
            "next_dose": None,
            "next_dose_time": None,
        }

    def _calculate_streak(self, med_id: str, today: date) -> int:
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
        await self._store.async_save(
            {
                "medications": self._medications,
                "dose_log": self._dose_log,
                CONF_NOTIFICATIONS: self._notification_config,
            }
        )
