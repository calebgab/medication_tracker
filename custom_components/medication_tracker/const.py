"""Constants for the Medication Tracker integration."""

DOMAIN = "medication_tracker"
PLATFORMS = ["sensor", "binary_sensor"]

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
