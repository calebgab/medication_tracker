"""Constants for the Medication Tracker integration."""

DOMAIN = "medication_tracker"
PLATFORMS = ["sensor", "binary_sensor", "button"]

# Config keys
CONF_MEDICATIONS = "medications"
CONF_MED_NAME = "name"
CONF_MED_DOSE = "dose"
CONF_MED_TIMES = "times"  # list of "HH:MM" strings
CONF_MED_DAYS = "days"  # list of weekday ints 0-6, empty = every day
CONF_MED_NOTES = "notes"

# Storage
STORAGE_KEY = "medication_tracker_data"
STORAGE_VERSION = 1

# Sensor unique id suffixes
SUFFIX_NEXT_DOSE = "next_dose"
SUFFIX_LAST_TAKEN = "last_taken"
SUFFIX_STREAK = "streak"
SUFFIX_TAKEN_TODAY = "taken_today"
SUFFIX_DUE = "due"
SUFFIX_OVERDUE = "overdue"
SUFFIX_MARK_TAKEN = "mark_taken"
SUFFIX_MARK_SKIPPED = "mark_skipped"

# Services
SERVICE_MARK_TAKEN = "mark_taken"
SERVICE_MARK_SKIPPED = "mark_skipped"
SERVICE_RESET_TODAY = "reset_today"

# Attr keys used in service calls & state attributes
ATTR_MEDICATION_ID = "medication_id"
ATTR_TAKEN_AT = "taken_at"
ATTR_DOSE = "dose"
ATTR_NOTES = "notes"
ATTR_SCHEDULED_TIME = "scheduled_time"
ATTR_TIMES = "times"
ATTR_DAYS = "days"
ATTR_STREAK = "streak"
ATTR_LAST_TAKEN = "last_taken"
ATTR_NEXT_DOSE = "next_dose"
ATTR_TAKEN_TODAY = "taken_today"
ATTR_SKIPPED_TODAY = "skipped_today"

# How many minutes past a scheduled time before it's considered overdue
OVERDUE_GRACE_MINUTES = 30
# How many minutes before a scheduled time to show "due soon"
DUE_SOON_MINUTES = 60

DAYS_OF_WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Medication types
MED_TYPE_SCHEDULED = "scheduled"
MED_TYPE_AS_NEEDED = "as_needed"
CONF_MED_TYPE = "med_type"

# PRN config keys
CONF_AS_NEEDED_MAX_PER_DAY = "as_needed_max_per_day"
CONF_AS_NEEDED_MAX_PER_24H = "as_needed_max_per_24h"
CONF_AS_NEEDED_MIN_HOURS = "as_needed_min_hours"

# PRN sensor/binary sensor suffixes
SUFFIX_NEXT_AVAILABLE = "next_available"
SUFFIX_AVAILABLE = "available"

# PRN defaults
DEFAULT_AS_NEEDED_MAX_PER_DAY = 4
DEFAULT_AS_NEEDED_MAX_PER_24H = 4
DEFAULT_AS_NEEDED_MIN_HOURS = 4

# ---------------------------------------------------------------------------
# Notification config keys
# ---------------------------------------------------------------------------

# Top-level notification config stored in coordinator
CONF_NOTIFICATIONS = "notifications"

# Global defaults keys
CONF_NOTIF_TARGET = "notify_target"
CONF_NOTIF_OVERDUE_ENABLED = "overdue_enabled"
CONF_NOTIF_OVERDUE_DELAY = "overdue_delay_minutes"
CONF_NOTIF_OVERDUE_TITLE = "overdue_title"
CONF_NOTIF_OVERDUE_MESSAGE = "overdue_message"
CONF_NOTIF_DUE_SOON_ENABLED = "due_soon_enabled"
CONF_NOTIF_DUE_SOON_TITLE = "due_soon_title"
CONF_NOTIF_DUE_SOON_MESSAGE = "due_soon_message"
CONF_NOTIF_TAKEN_ENABLED = "taken_enabled"
CONF_NOTIF_TAKEN_TITLE = "taken_title"
CONF_NOTIF_TAKEN_MESSAGE = "taken_message"

# Per-medication override keys
CONF_NOTIF_OVERRIDES = "notification_overrides"
CONF_NOTIF_OVERRIDE_OVERDUE = "override_overdue"
CONF_NOTIF_OVERRIDE_DUE_SOON = "override_due_soon"
CONF_NOTIF_OVERRIDE_TAKEN = "override_taken"

# Default notify target
DEFAULT_NOTIFY_TARGET = "notify.persistent_notification"
DEFAULT_OVERDUE_DELAY = 0

# Default message templates
# Available placeholders: {medication}, {dose}, {time}, {overdue_since}
DEFAULT_OVERDUE_TITLE = "{medication} overdue"
DEFAULT_OVERDUE_MESSAGE = "{medication} ({dose}) was due at {overdue_since} and hasn't been taken."
DEFAULT_DUE_SOON_TITLE = "{medication} due soon"
DEFAULT_DUE_SOON_MESSAGE = "{medication} ({dose}) is due at {time}."
DEFAULT_TAKEN_TITLE = "{medication} taken"
DEFAULT_TAKEN_MESSAGE = "{medication} ({dose}) has been marked as taken."
