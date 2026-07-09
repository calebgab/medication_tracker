# <img src="custom_components/medication_tracker/brand/icon.png" alt="" height="32"/> Medication Tracker for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/release/calebgab/medication_tracker.svg)](https://github.com/calebgab/medication_tracker/releases)
[![CI](https://github.com/calebgab/medication_tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/calebgab/medication_tracker/actions/workflows/ci.yml)

Track medications, scheduled doses, streaks, and overdue alerts — entirely local, no cloud, no app required.

---

## Features

- **Two medication types** — scheduled (fixed times of day) and as-needed/PRN (dose-limit tracking)
- **Sensors** for next dose time, last taken timestamp, streak (consecutive days taken), and doses taken today
- **Binary sensors** for overdue detection (with configurable grace period) and due-soon alerts (within 60 minutes) for scheduled meds; availability tracking for PRN meds
- **Button entities** to mark doses as taken or skipped — appear automatically on the device page
- **Built-in notifications** — configure overdue, due soon, and taken confirmation alerts directly from the integration, with actionable notifications (Mark taken / Remind in 5 min) on iOS and Android
- **Per-medication notification overrides** — enable or disable individual alert types per medication, overriding the global settings
- **Services** to mark doses taken or skipped, and reset today's log
- **Full UI configuration** — add, edit, and remove medications via the Home Assistant UI (no YAML required)
- **Optional Lovelace card** — a custom dashboard card showing all medications with status and action buttons
- **Persistent storage** — survives restarts; today's log is pruned automatically at midnight

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations
2. Search for **Medication Tracker** and install
3. Restart Home Assistant

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
| Medication type | Scheduled or as-needed | `Scheduled` |
| Notes | Optional reminder notes | `Take with food` |

Depending on the type selected, you will then be prompted for type-specific settings (see below).

### Scheduled medications

| Field | Description | Example |
|-------|-------------|---------|
| Scheduled times | Comma-separated HH:MM (24-hour) | `08:00, 20:00` |
| Days | Days of week (leave blank = every day) | `mon, wed, fri` |

Days can be entered as `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`.

### As-needed (PRN) medications

As-needed medications have no fixed schedule. Instead you configure dose limits and the integration tracks availability and usage.

| Field | Description | Example |
|-------|-------------|---------|
| Max doses per day | Calendar-day maximum | `4` |
| Max doses per 24 hours | Rolling 24-hour window maximum | `4` |
| Minimum hours between doses | Minimum gap between any two doses | `4` |

When any limit is reached the `available` binary sensor turns `off` and the `next_available` sensor shows when the medication can next be taken.

### Notifications

Click **Configure** on the integration card, then choose **Notifications** to set up alerts. No automations required — notifications are fired directly by the integration.

| Setting | Description |
|---------|-------------|
| Notify service | The HA notify service to use (e.g. `notify.mobile_app_your_phone`) — select from the dropdown of detected devices |
| Alert when due | Send a notification when a dose is due |
| Alert when overdue | Send a notification when a dose is past its grace period |
| Overdue delay | Extra minutes to wait after the grace period before notifying (0 = immediate) |
| Alert when due soon | Send a notification when a dose is due within 60 minutes |
| Taken confirmation | Send a notification when a dose is marked as taken |

Notifications on iOS and Android include **Mark taken** and **Remind in 5 min** action buttons. Tapping Mark taken updates the sensors immediately without opening the app.

After the global settings, you can also customise the notification title and message templates for each alert type.

#### Per-medication notification overrides

After configuring global notification settings, choose **Per-medication overrides** from the Notifications menu and select a medication. You can then enable or disable each alert type individually for that medication, overriding whatever the global setting is.

**Available placeholders in message templates:**

| Placeholder | Description |
|-------------|-------------|
| `{medication}` | Medication name |
| `{dose}` | Dose description |
| `{time}` | Scheduled time |
| `{overdue_since}` | Time the dose became overdue |

---

## Entities

### Scheduled medications

| Entity | Description |
|--------|-------------|
| `sensor.<name>_next_dose` | Datetime of the next scheduled dose |
| `sensor.<name>_last_taken` | Datetime the medication was last marked taken |
| `sensor.<name>_streak` | Consecutive days with at least one dose taken |
| `sensor.<name>_taken_today` | Number of doses taken today |
| `binary_sensor.<name>_overdue` | `on` when a scheduled dose is past its grace period with no entry |
| `binary_sensor.<name>_due_soon` | `on` when the next dose is within 60 minutes |
| `button.<name>_mark_taken` | Mark the current dose as taken |
| `button.<name>_mark_skipped` | Mark the current dose as skipped |

### As-needed (PRN) medications

| Entity | Description |
|--------|-------------|
| `sensor.<name>_next_available` | Datetime when the medication can next be taken (absent if available now) |
| `sensor.<name>_last_taken` | Datetime the medication was last marked taken |
| `sensor.<name>_streak` | Consecutive days with at least one dose taken |
| `sensor.<name>_taken_today` | Number of doses taken today |
| `binary_sensor.<name>_available` | `on` when the medication is within all dose limits and can be taken |
| `button.<name>_mark_taken` | Record a dose taken now |
| `button.<name>_mark_skipped` | Mark a dose as skipped |

### State Attributes

The `next_dose` sensor includes:
- `times` — all scheduled times
- `scheduled_time` — the specific upcoming slot
- `dose` — dose description
- `notes` — any notes

The `overdue` binary sensor includes:
- `overdue_since` — ISO datetime of the missed scheduled slot

The `next_available` sensor includes:
- `as_needed_max_per_day` — configured daily maximum
- `as_needed_max_per_24h` — configured 24-hour rolling maximum
- `as_needed_min_hours` — configured minimum gap between doses

---

## Services

### `medication_tracker.mark_taken`

Record that a dose was taken.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `medication_id` | ✅ | The medication's unique ID (see below) |
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

---

## Optional: Lovelace Dashboard Card

A custom card is available that shows all your medications in one place, including status, next dose time, last taken, streak, doses taken today, and Mark taken / Skip dose buttons.

![Medication Tracker Lovelace Card](docs/lovelace-card.png)

> **Note:** This card is optional and requires a one-time manual step. It is not installed automatically by HACS.

### Installation

1. Copy `www/medication-tracker-card.js` from this directory into your Home Assistant `www` folder (i.e. `config/www/medication-tracker-card.js`)
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
          title: "Good morning!"
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

A scheduled dose is not considered overdue until **30 minutes** after its scheduled time, to account for slight delays. The due-soon window is **60 minutes** before a scheduled dose.

---

## Troubleshooting

**I can't find the medication_id**
Open Developer Tools → States, find any entity for your medication (e.g. `sensor.aspirin_next_dose`), and look in the **Attributes** panel. You can also use a template:
```yaml
{{ state_attr('sensor.aspirin_next_dose', 'medication_id') }}
```

**The overdue sensor isn't triggering**
Check that your scheduled times are in `HH:MM` 24-hour format and that your HA timezone is set correctly (**Settings → System → General**).

**Entities disappeared after a restart**
This should not happen — medications are persisted in HA's `.storage` directory. If it does, check the HA logs for errors from the `medication_tracker` domain.

**Notifications aren't working**
Check that you have selected a notify target in **Configure → Notifications** and that the relevant toggles (overdue, due soon) are enabled. The notify service name must exactly match a service listed in Developer Tools → Services under `notify.`.

**The Lovelace card isn't appearing in the card picker**
Make sure the resource was added correctly (**Settings → Dashboards → Resources**) and that you did a full page reload after adding it.

---

## License

MIT
