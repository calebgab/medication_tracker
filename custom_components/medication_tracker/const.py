"""Constants for the Medication Tracker integration."""

DOMAIN = "medication_tracker"
PLATFORMS = ["sensor", "binary_sensor", "button", "number"]

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
SUFFIX_STOCK = "stock"
SUFFIX_LOW_STOCK = "low_stock"
SUFFIX_STOCK_NUMBER = "stock_number"

# Services
SERVICE_MARK_TAKEN = "mark_taken"
SERVICE_MARK_SKIPPED = "mark_skipped"
SERVICE_RESET_TODAY = "reset_today"
SERVICE_ADJUST_STOCK = "adjust_stock"

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
ATTR_AMOUNT = "amount"
ATTR_CURRENT_STOCK = "current_stock"

# Stock tracking config keys (per medication, opt-in)
CONF_STOCK_TRACKING_ENABLED = "stock_tracking_enabled"
CONF_CURRENT_STOCK = "current_stock"
CONF_STOCK_PER_DOSE = "stock_per_dose"
CONF_STOCK_LOW_THRESHOLD = "stock_low_threshold"

DEFAULT_STOCK_PER_DOSE = 1.0
DEFAULT_STOCK_LOW_THRESHOLD = 5.0

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
CONF_NOTIF_DUE_ENABLED = "due_enabled"
CONF_NOTIF_DUE_TITLE = "due_title"
CONF_NOTIF_DUE_MESSAGE = "due_message"
CONF_NOTIF_LOW_STOCK_ENABLED = "low_stock_enabled"
CONF_NOTIF_LOW_STOCK_TITLE = "low_stock_title"
CONF_NOTIF_LOW_STOCK_MESSAGE = "low_stock_message"

# ---------------------------------------------------------------------------
# Notification sounds (per alert type, per platform)
# ---------------------------------------------------------------------------

# iOS sound modes
SOUND_MODE_DEFAULT = "default"
SOUND_MODE_CRITICAL = "critical"
SOUND_MODE_TIME_SENSITIVE = "time_sensitive"
SOUND_MODE_NONE = "none"

IOS_SOUND_MODE_OPTIONS = {
    SOUND_MODE_DEFAULT: "Default (device's normal notification sound)",
    SOUND_MODE_CRITICAL: "Critical — bypasses mute & Do Not Disturb",
    SOUND_MODE_TIME_SENSITIVE: "Time-sensitive — plays a sound",
    SOUND_MODE_NONE: "No sound",
}

# Android only has Default/Critical/None — sound itself isn't payload-settable,
# only the notification channel + importance, which the user then configures
# on-device (see ANDROID_CRITICAL_CHANNEL / ANDROID_SILENT_CHANNEL below).
ANDROID_SOUND_MODE_OPTIONS = {
    SOUND_MODE_DEFAULT: "Default (device's normal notification sound)",
    SOUND_MODE_CRITICAL: "Critical — dedicated high-priority channel",
    SOUND_MODE_NONE: "No sound",
}

ANDROID_IMPORTANCE_OPTIONS = {
    "min": "Min",
    "low": "Low",
    "default": "Default",
    "high": "High",
    "max": "Max",
}

DEFAULT_IOS_SOUND_MODE = SOUND_MODE_DEFAULT
DEFAULT_IOS_SOUND_NAME = "default"
DEFAULT_ANDROID_SOUND_MODE = SOUND_MODE_DEFAULT
DEFAULT_ANDROID_IMPORTANCE = "default"

# Critical alerts require the user to have granted the HA app "Critical
# Alerts" permission in iOS Settings, separate from ordinary notification
# permission — bypasses mute and Do Not Disturb when granted.
IOS_CRITICAL_SOUND = {"name": "default", "critical": 1, "volume": 1.0}

# Android channels are created once (on first send) and locked from then on —
# later importance/sound changes via the payload are ignored, only lowering
# takes effect. Users adjust sound per-channel in their device's own settings.
ANDROID_CRITICAL_CHANNEL = "Critical Medication"
ANDROID_SILENT_CHANNEL = "Medication Tracker (Silent)"
ANDROID_SILENT_IMPORTANCE = "low"

# Per-alert-type sound config keys
CONF_NOTIF_DUE_IOS_SOUND_MODE = "due_ios_sound_mode"
CONF_NOTIF_DUE_IOS_SOUND_NAME = "due_ios_sound_name"
CONF_NOTIF_DUE_ANDROID_SOUND_MODE = "due_android_sound_mode"
CONF_NOTIF_DUE_ANDROID_IMPORTANCE = "due_android_importance"

CONF_NOTIF_OVERDUE_IOS_SOUND_MODE = "overdue_ios_sound_mode"
CONF_NOTIF_OVERDUE_IOS_SOUND_NAME = "overdue_ios_sound_name"
CONF_NOTIF_OVERDUE_ANDROID_SOUND_MODE = "overdue_android_sound_mode"
CONF_NOTIF_OVERDUE_ANDROID_IMPORTANCE = "overdue_android_importance"

CONF_NOTIF_DUE_SOON_IOS_SOUND_MODE = "due_soon_ios_sound_mode"
CONF_NOTIF_DUE_SOON_IOS_SOUND_NAME = "due_soon_ios_sound_name"
CONF_NOTIF_DUE_SOON_ANDROID_SOUND_MODE = "due_soon_android_sound_mode"
CONF_NOTIF_DUE_SOON_ANDROID_IMPORTANCE = "due_soon_android_importance"

CONF_NOTIF_TAKEN_IOS_SOUND_MODE = "taken_ios_sound_mode"
CONF_NOTIF_TAKEN_IOS_SOUND_NAME = "taken_ios_sound_name"
CONF_NOTIF_TAKEN_ANDROID_SOUND_MODE = "taken_android_sound_mode"
CONF_NOTIF_TAKEN_ANDROID_IMPORTANCE = "taken_android_importance"

CONF_NOTIF_LOW_STOCK_IOS_SOUND_MODE = "low_stock_ios_sound_mode"
CONF_NOTIF_LOW_STOCK_IOS_SOUND_NAME = "low_stock_ios_sound_name"
CONF_NOTIF_LOW_STOCK_ANDROID_SOUND_MODE = "low_stock_android_sound_mode"
CONF_NOTIF_LOW_STOCK_ANDROID_IMPORTANCE = "low_stock_android_importance"

# Per alert-type field key groups, used to build the sound schema/payload
# generically instead of repeating the same 4-field block five times.
NOTIF_SOUND_KEYS_BY_TYPE = {
    "due": (
        CONF_NOTIF_DUE_IOS_SOUND_MODE,
        CONF_NOTIF_DUE_IOS_SOUND_NAME,
        CONF_NOTIF_DUE_ANDROID_SOUND_MODE,
        CONF_NOTIF_DUE_ANDROID_IMPORTANCE,
    ),
    "overdue": (
        CONF_NOTIF_OVERDUE_IOS_SOUND_MODE,
        CONF_NOTIF_OVERDUE_IOS_SOUND_NAME,
        CONF_NOTIF_OVERDUE_ANDROID_SOUND_MODE,
        CONF_NOTIF_OVERDUE_ANDROID_IMPORTANCE,
    ),
    "due_soon": (
        CONF_NOTIF_DUE_SOON_IOS_SOUND_MODE,
        CONF_NOTIF_DUE_SOON_IOS_SOUND_NAME,
        CONF_NOTIF_DUE_SOON_ANDROID_SOUND_MODE,
        CONF_NOTIF_DUE_SOON_ANDROID_IMPORTANCE,
    ),
    "taken": (
        CONF_NOTIF_TAKEN_IOS_SOUND_MODE,
        CONF_NOTIF_TAKEN_IOS_SOUND_NAME,
        CONF_NOTIF_TAKEN_ANDROID_SOUND_MODE,
        CONF_NOTIF_TAKEN_ANDROID_IMPORTANCE,
    ),
    "low_stock": (
        CONF_NOTIF_LOW_STOCK_IOS_SOUND_MODE,
        CONF_NOTIF_LOW_STOCK_IOS_SOUND_NAME,
        CONF_NOTIF_LOW_STOCK_ANDROID_SOUND_MODE,
        CONF_NOTIF_LOW_STOCK_ANDROID_IMPORTANCE,
    ),
}

# Per-medication override keys
CONF_NOTIF_OVERRIDES = "notification_overrides"
CONF_NOTIF_OVERRIDE_OVERDUE = "override_overdue"
CONF_NOTIF_OVERRIDE_DUE_SOON = "override_due_soon"
CONF_NOTIF_OVERRIDE_TAKEN = "override_taken"
CONF_NOTIF_OVERRIDE_DUE = "override_due"
CONF_NOTIF_OVERRIDE_LOW_STOCK = "override_low_stock"

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
DEFAULT_DUE_TITLE = "{medication} due now"
DEFAULT_DUE_MESSAGE = "{medication} ({dose}) is due now."
DEFAULT_LOW_STOCK_TITLE = "{medication} low on stock"
DEFAULT_LOW_STOCK_MESSAGE = "{medication} ({dose}) has {stock} unit(s) left — time to restock."
