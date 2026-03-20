# Medication Tracker for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/calebgab/medication_tracker.svg)](https://github.com/calebgab/medication_tracker/releases)
[![CI](https://github.com/calebgab/medication_tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/calebgab/medication_tracker/actions/workflows/ci.yml)

Track medications, scheduled doses, streaks, and overdue alerts — entirely local, no cloud, no app required.

---

## Features

- **Multiple medications** with individual schedules (times of day, specific days of week)
- **Sensors** for next dose time, last taken timestamp, streak (consecutive days taken), and doses taken today
- **Binary sensors** for overdue detection (with configurable grace period) and due-soon alerts (within 60 minutes)
- **Button entities** to mark doses as taken or skipped — appear automatically on the device page
- **Built-in notifications** — configure overdue, due soon, and taken confirmation alerts directly from the integration, with actionable notifications (Mark taken / Remind in 5 min) on iOS and Android
- **Services** to mark doses taken or skipped, and reset today's log
- **Full UI configuration** — add, edit, and remove medications via the Home Assistant UI (no YAML required)
- **Optional Lovelace card** — a custom dashboard card showing all medications with status and action buttons
- **Persistent storage** — survives restarts; today's log is pruned automatically at midnight

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations
2. Click the **⋮** menu → **Custom repositories**
3. Add `https://github.com/calebgab/medication_tracker` with category **Integration**
4. Search for **Medication Tracker** and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/medication_tracker/` folder into your HA `custom_components/` directory
2. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Medication Tracker**
3. Give it a name (useful if you want multiple trackers, e.g. one per person)
4. Click **Configure** to add your first medication

---

## Configuration

### Adding a medication

Click **Configure** on the integration card, choose **Add new medication**, and fill in:

| Field | Description | Example |
|-------|-------------|---------|
| Name | Medication name | `Aspirin` |
| Dose | Optional dose description | `100mg` |
| Scheduled times | Comma-separated HH:MM | `08:00, 20:00` |
| Days | Days of week (leave blank = every day) | `mon, wed, fri` |
| Notes | Optional reminder notes | `Take with food` |

Days can be entered as `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` (or `0`–`6`).

### Notifications

Click **Configure** on the integration card, then choose **Notifications** to set up alerts. No automations required — notifications are fired directly by the integration.

| Setting | Description |
|---------|-------------|
| Notify service | The HA notify service to use (e.g. `notify.mobile_app_your_phone`) — select from the dropdown of detected devices |
| Alert when overdue | Send a notification when a dose is past its grace period |
| Overdue delay | Extra minutes to wait after the grace period before notifying (0 = immediate) |
| Alert when due soon | Send a notification when a dose is due within 60 minutes |
| Taken confirmation | Send a notification when a dose is marked as taken |

Notifications on iOS and Android include **Mark taken** and **Remind in 5 min** action buttons. Tapping Mark taken updates the sensors immediately without opening the app.

You can also customise the notification title and message templates, and override notification settings per medication.

**Available placeholders in message templates:**

| Placeholder | Description |
|-------------|-------------|
| `{medication}` | Medication name |
| `{dose}` | Dose description |
| `{time}` | Scheduled time |
| `{overdue_since}` | Time the dose became overdue |

---

## Entities

For each medication, the following entities are created (grouped under one device per medication):

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.<name>_next_dose` | Datetime of the next scheduled dose |
| `sensor.<name>_last_taken` | Datetime the medication was last marked taken |
| `sensor.<name>_streak` | Consecutive days with at least one dose taken |
| `sensor.<name>_taken_today` | Number of doses taken today |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.<name>_overdue` | `on` when a scheduled dose is past its grace period with no entry |
| `binary_sensor.<name>_due_soon` | `on` when the next dose is within 60 minutes |

### Buttons

| Entity | Description |
|--------|-------------|
| `button.<name>_mark_taken` | Mark the current dose as taken |
| `button.<name>_mark_skipped` | Mark the current dose as skipped |

Buttons appear automatically on the device page and can be added to any Lovelace dashboard.

### State Attributes

The `next_dose` sensor includes:
- `times` — all scheduled times
- `scheduled_time` — the specific upcoming slot
- `dose` — dose description
- `notes` — any notes

The `overdue` binary sensor includes:
- `overdue_since` — ISO datetime of the missed scheduled slot

---

## Services

### `medication_tracker.mark_taken`

Record that a dose was taken.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `medication_id` | ✅ | The medication's unique ID (from entity attributes) |
| `scheduled_time` | ❌ | Which scheduled slot this applies to (HH:MM) |
| `taken_at` | ❌ | When it was taken (ISO datetime, defaults to now) |

### `medication_tracker.mark_skipped`

Record that a scheduled dose was intentionally skipped (prevents overdue alert for that slot).

| Parameter | Required | Description |
|-----------|----------|-------------|
| `medication_id` | ✅ | The medication's unique ID |
| `scheduled_time` | ❌ | Which scheduled slot is being skipped |

### `medication_tracker.reset_today`

Clear all taken/skipped entries for today for a given medication.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `medication_id` | ✅ | The medication's unique ID |

### Finding the medication_id

The `medication_id` is shown in the **state attributes** of any entity for that medication. You can also use a template:

```yaml
{{ state_attr('sensor.aspirin_next_dose', 'medication_id') }}
```

Or look it up via the **Developer Tools → States** panel.

---

## Optional: Lovelace Dashboard Card

A custom card is available that shows all your medications in one place, including status, next dose time, last taken, streak, doses taken today, and Mark taken / Skip dose buttons.

> **Note:** This card is optional and requires a one-time manual step. It is not installed automatically by HACS.

### Installation

1. Copy `www/medication-tracker-card.js` from the [releases page](https://github.com/calebgab/medication_tracker/releases) into your Home Assistant `www` folder (i.e. `config/www/medication-tracker-card.js`)
2. Go to **Settings → Dashboards → Resources**
3. Click **Add resource**
4. Set URL to `/local/medication-tracker-card.js` and type to **JavaScript module**
5. Click **Create** then reload the page

### Adding the card to a dashboard

1. Edit any dashboard
2. Click **Add card**
3. Scroll to the bottom and select **Custom: Medication Tracker**
4. The card automatically discovers all your medications — no configuration needed

---

## Automation Examples

### Reminder notification when overdue

```yaml
automation:
  - alias: "Medication overdue alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.aspirin_overdue
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "💊 Medication Reminder"
          message: "Aspirin is overdue! Don't forget to take it."
```

### Mark taken via NFC tap

```yaml
automation:
  - alias: "NFC tag - mark aspirin taken"
    trigger:
      - platform: tag
        tag_id: "your-nfc-tag-id"
    action:
      - service: medication_tracker.mark_taken
        data:
          medication_id: "your-medication-id-here"
```

### Morning briefing — show streak

```yaml
automation:
  - alias: "Morning medication briefing"
    trigger:
      - platform: time
        at: "07:50:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.aspirin_streak
        above: 0
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "💊 Good morning!"
          message: >
            Aspirin due at 08:00. Current streak:
            {{ states('sensor.aspirin_streak') }} days. Keep it up!
```

### Dashboard button to mark taken (tap-action)

```yaml
type: button
name: Mark Aspirin Taken
icon: mdi:pill
tap_action:
  action: call-service
  service: button.press
  target:
    entity_id: button.aspirin_mark_taken
```

---

## Overdue Grace Period

By default, a dose is not considered **overdue** until **30 minutes** after its scheduled time (to account for slight delays). This constant is defined in `const.py` as `OVERDUE_GRACE_MINUTES = 30`.

The **due soon** window is **60 minutes** before a scheduled dose (`DUE_SOON_MINUTES = 60`).

---

## Troubleshooting

**I can't find the medication_id**
Open Developer Tools → States, find any entity for your medication (e.g. `sensor.aspirin_next_dose`), and look in the **Attributes** panel.

**The overdue sensor isn't triggering**
Check that your scheduled times are in `HH:MM` 24-hour format and that your HA timezone is set correctly (**Settings → System → General**).

**Entities disappeared after a restart**
This should not happen — medications are persisted in HA's `.storage` directory. If it does, check the HA logs for errors from the `medication_tracker` domain.

**Notifications aren't working**
Check that you have selected a notify target in **Configure → Notifications** and that the relevant toggles (overdue, due soon) are enabled. The notify service name must exactly match a service listed in Developer Tools → Services under `notify.`.

**The Lovelace card isn't appearing in the card picker**
Make sure the resource was added correctly (**Settings → Dashboards → Resources**) and that you did a full page reload after adding it.

---

## Contributing

PRs welcome. Please lint before submitting:

```bash
pip install ruff
ruff check custom_components/
```

---

## License

MIT