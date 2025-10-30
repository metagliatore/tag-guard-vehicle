# Vehicle BT Parking Sentinel

Home Assistant integration to monitor and protect your vehicle using a Bluetooth tracker (SmartTag, AirTag, Tile, etc.). Automatically saves parking location, sends notifications on unauthorized movement, and provides remote control via webhook API.

## 📑 Table of Contents
- [Quick Start](#quick-start)
- [Activation Modes](#activation-mo**State transitions:**
- `parked` / `alarm_triggered` → `position_saved`
- If no position saved → `unknown`

**Note:** Previously called `disarm` - renamed to `stop` for clarity.

#### 🔇 **mute** - Silence Notifications (Keep Monitoring)  - [Practical Examples](#practical-examples)
- [Sensor States](#sensor-states)
- [Features](#features)
- [Webhook API](#webhook-api)
- [Services](#services)
- [Best Practices and Common Use Cases](#best-practices-and-common-use-cases)
- [Lovelace Cards](#lovelace-and-cards)
- [Debugging and Logging](#debugging-and-logging)
- [Installation and Testing](#installation-and-local-testing)
- [Translations](#translations)

## Quick Start

### Installation
1. Copy `custom_components/vehicle_bt_parking_sentinel` to your Home Assistant `custom_components` folder
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Vehicle BT Parking Sentinel"
5. Follow the wizard:
   - Select your `device_tracker` entity (e.g., SmartTag)
   - Choose activation mode (start with `combined` for reliability)
   - Configure notification service
   - Set tolerance radius (default: 200m)

### First Test
After setup, test the integration:

```yaml
# Developer Tools → Services
service: vehicle_bt_parking_sentinel.start
data:
  notify_waiting: true  # Optional: get notification if waiting for GPS
```

Check the sensor: `sensor.<entry_id>_vehicle_status` should show:
- `state: parked` (or `awaiting_position` if GPS is stale)
- `alarm_active: true`
- `saved_latitude` and `saved_longitude` populated

Now move your device_tracker beyond `tolerance_radius` → you should receive a notification!

## Activation modes
The integration supports several activation modes (option `activation_mode`). **All modes determine WHEN to save the parking position and enable monitoring (alarm).**

- **`connection`** — Saves position and enables monitoring immediately when the `device_tracker` disconnects (fast, does not use stationary checks).
- **`position`** — Monitors reported coordinates and uses stationary checks (`stationary_minutes` + `stationary_count`) to confirm a stable position before saving and enabling monitoring.
- **`combined`** — Requires both a disconnect event AND stationary confirmation before saving and enabling monitoring (recommended for fewer false positives).
- **`manual`** — No automatic triggers; only manual activation via the `start` service or webhook.

**Important**: The `start` service is available in ALL modes, not just `manual` mode. It provides a quick way to manually save position and enable monitoring regardless of the configured activation mode. In `manual` mode, it's the only way to activate monitoring; in other modes, it acts as an additional manual override.

**Advanced**: The `start` service accepts an optional `notify_waiting: true` parameter to receive a notification if the system is waiting for a fresh GPS position (useful for manual UI triggers).

**In all modes**, once the position is saved and monitoring is enabled, the integration will send a notification if the vehicle moves beyond the configured `tolerance_radius`.

Choose `position` or `combined` for conservative behavior; choose `connection` for more reactive saves; choose `manual` for full control.

### Practical Examples

#### Example 1: Using `connection` mode with automatic activation
When configured with `activation_mode: connection`, the integration automatically saves and enables monitoring when the BT tag disconnects:

1. You park your vehicle → BT tag disconnects
2. Integration saves current GPS position
3. Alarm is enabled automatically
4. If vehicle moves beyond `tolerance_radius` → notification sent

No automation needed - it's fully automatic.

#### Example 2: Using `manual` mode with button/automation
Configure the integration with `activation_mode: manual` for full control. Example automation to activate when you press a button:

```yaml
automation:
  - alias: "Activate Vehicle Parking Monitoring"
    trigger:
      - platform: state
        entity_id: input_button.park_vehicle
        # Or use: platform: event with mobile app notification action
    action:
      - service: vehicle_bt_parking_sentinel.start
        data:
          notify_waiting: true  # Get notification if waiting for GPS
```

This will:
1. Read current GPS position from `device_tracker`
2. Save position (only if GPS timestamp is fresh)
3. Enable alarm
4. If GPS is stale, wait for next fresh GPS reading before saving

#### Example 3: Using `combined` mode for reliability
Configure with `activation_mode: combined` to require both disconnect AND stationary confirmation. This avoids false positives when you stop briefly at traffic lights:

1. You park → BT disconnects (first condition met)
2. Integration monitors GPS position
3. After `stationary_count` readings within `tolerance_radius` over `stationary_minutes` → saves position and enables alarm

#### Example 4: Disable monitoring when leaving parking
Use an automation to disable the alarm when you return to the vehicle:

```yaml
automation:
  - alias: "Disable Parking Monitoring When Entering Vehicle"
    trigger:
      - platform: state
        entity_id: device_tracker.smarttag_scooter
        to: "home"  # Or check connection state
    action:
      - service: vehicle_bt_parking_sentinel.toggle_alarm
        data: {}
```

Or use the webhook from your phone:
```bash
curl -X POST -d '{"action":"stop"}' https://your-ha.com/api/webhook/<token>
```

#### Example 5: Manual override in `combined` mode
Even when using `combined` mode for automatic activation, you can force immediate activation using `start`:

```yaml
automation:
  - alias: "Force Parking Activation (Override Combined Mode)"
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: force_park
    action:
      - service: vehicle_bt_parking_sentinel.start
        data:
          notify_waiting: true  # Optional: notify if waiting for GPS
```

This is useful when:
- You're parking in a location where the tag might not disconnect
- You want to activate monitoring before the stationary timer completes
- You're testing the integration

---

## Sensor States

The integration sensor has **5 possible states** that reflect the current monitoring status:

### 🔴 `unknown`
**Initial state - System not configured**
- ❌ No saved position
- ❌ Alarm not active

**When it appears:**
- First installation
- After `clear_persisted` service
- After `disarm` when no position is saved

---

### ⏳ `awaiting_position`
**Waiting to save GPS position**
- ✅ Alarm active
- ❌ No position saved (or waiting for fresh GPS)

**When it appears:**
- Immediately after `start` command (before GPS update arrives)
- When GPS is stale and waiting for a fresh reading
- During stationary detection phase (candidate position not yet saved)

**Automatic transition to `parked`:**
- When a valid GPS position is successfully saved

---

### 🅿️ `parked`
**Active monitoring - Vehicle parked**
- ✅ Alarm active
- ✅ Position saved
- ❌ No movement detected

**When it appears:**
- After `start` successfully saves position
- When alarm is monitoring for movements
- After `save` if alarm was already active

**Automatic transition to `alarm_triggered`:**
- When movement beyond tolerance is detected

---

### 🚨 `alarm_triggered`
**Alarm fired - Movement detected!**
- ✅ Alarm active
- ✅ Position saved
- ✅ Movement detected (`position_notified = True`)

**When it appears:**
- When vehicle moves beyond tolerance radius
- Notification has been sent

**How to reset:**
- `disarm` → returns to `position_saved` (or `unknown` if position cleared)
- `unmute` → returns to `parked` (resets `position_notified` flag)

---

### 📍 `position_saved`
**Position stored but alarm disabled**
- ❌ Alarm not active
- ✅ Position saved

**When it appears:**
- After `disarm` when a position is saved
- After `save` when alarm is not active (manual mode)
- When monitoring is stopped but position is kept

**Manual transition to `parked`:**
- `start` command → activates alarm → becomes `parked`

---

### State Transition Diagram

```
unknown
   │
   ├──[start]──> awaiting_position ──[GPS arrives]──> parked
   │                                                     │
   │                                                     │
   └──[save]──> position_saved ──[start]──> ────────────┘
                      │                                  │
                      │                             [movement]
                      │                                  │
                      └──[start]──> parked ──────> alarm_triggered
                                        │                │
                                        │                │
                                   [disarm]         [unmute]
                                        │                │
                                        └────────────────┘
```

---

## Features

- Automatic parking detection based on a `device_tracker` entity.
- Persistent saved position (latitude/longitude) with metadata fields: `saved_gpsUtcDt`, `saved_location_type`, `saved_last_seen`.
- Stationary detection (`stationary_minutes`, `stationary_count`) to avoid saving transient locations.
- Notification support via a configured `notify` service (includes Google Maps link).
- Webhook support: wizard can auto-generate a `webhook_token` and shows the full webhook URL.
- Helper services: `start`, `stop`, `save_position`, `reset_flags`, `clear_persisted`, `mute_notifications`, `unmute_notifications`, `get_webhook_info`.
- Lovelace support: sensor `sensor.<entry_id>_vehicle_status` exposes state and attributes; an example custom card and a styled `custom:button-card` are included.

## Webhook API

The integration provides a webhook for remote control (e.g., from mobile shortcuts, Tasker, IFTTT).

### Endpoint
```
POST https://YOUR_HA_IP:8123/api/webhook/<YOUR_WEBHOOK_TOKEN>
```

The **token is in the URL path** (not in headers). During setup, the wizard auto-generates a `webhook_token` and displays the full URL.

### Webhook Control Page (Browser)

Visit the webhook URL in a browser using **GET** to see an interactive control page with buttons:

```
GET https://YOUR_HA_IP:8123/api/webhook/<YOUR_WEBHOOK_TOKEN>
```

This shows a simple HTML page with buttons for **Start**, **Stop (Disarm)**, and **Trigger Save**. Click buttons to POST actions back to the webhook.

**Use case:** Quick testing without curl/Postman, or create mobile browser bookmarks for fast access.

---

### Supported Actions (POST)

Send a JSON payload with an `action` field in the **body** to control the sentinel:

#### 🟢 **start** - Enable Monitoring
Activates alarm and begins monitoring for movement.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"start"}' \
  https://YOUR_HA_IP:8123/api/webhook/<YOUR_WEBHOOK_TOKEN>
```

**Optional parameter `notify_waiting`** (boolean): Send notification if GPS is stale.

```bash
# With notification if waiting for GPS
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"start", "notify_waiting":true}' \
  https://YOUR_HA_IP:8123/api/webhook/<YOUR_WEBHOOK_TOKEN>
```

**Response:**
```json
{"status":"started","alarm_active":true,"notify_waiting":false}
```

**Behavior:**
- Activates alarm monitoring
- Saves position ONLY if GPS timestamp is fresh (newer than activation time)
- If GPS is stale, sets `awaiting_activation_save = true` and waits for next GPS update
- Sends notification "🟢 Monitoring activated" when position is saved
- If `notify_waiting:true` and GPS is stale, sends "⏳ Waiting for GPS position..." notification

**State transitions:**
- `unknown` → `awaiting_position` (then → `parked` when GPS arrives)
- `position_saved` → `parked` (if position already exists)

**⚠️ Important Notes:**
- In **manual mode** with parked vehicle, GPS may be stale
- `start` alone may NOT save position immediately
- **Recommended sequence for manual mode**: `save` → `start` (see below)
- Use `notify_waiting:true` to get immediate feedback if waiting for GPS

#### 💾 **save** - Save Position Immediately
Force-saves current position from device_tracker (always, regardless of GPS timestamp).

```bash
curl -X POST -d '{"action":"save"}' \
  https://YOUR_HA_IP:8123/api/webhook/<token>
```

**Response:**
```json
{"status":"saved","latitude":45.507,"longitude":9.249}
```

**Behavior:**
- Always saves position from device_tracker (regardless of GPS timestamp)
- Does NOT change alarm state
- Sends notification "📍 Position saved"

**State transitions:**
- `unknown` → `position_saved` (if alarm not active)
- Stays in current state if alarm is active

**Key difference from `start`:**
- `start`: Saves position conditionally (only if GPS is fresh)
- `save`: Saves position always (guaranteed)

**Best practice for manual mode:**
```bash
# 1. Save position first (guaranteed)
curl -X POST -d '{"action":"save"}' https://.../<token>

# 2. Then activate monitoring
curl -X POST -d '{"action":"start"}' https://.../<token>
```

#### 🔴 **stop** - Disable Monitoring
Completely stops monitoring and disables alarm.

```bash
curl -X POST -d '{"action":"stop"}' https://.../<token>
```

**Response:**
```json
{"status":"stopped","alarm_active":false,"message":"Alarm disabled. Monitoring stopped."}
```

**Behavior:**
- Disables alarm completely
- Stops monitoring for movements
- Does NOT send any notification (silent operation)
- Keeps saved position (moves to `position_saved` state)

**State transitions:**
- `parked` / `alarm_triggered` → `position_saved`
- If no position saved → `unknown`

#### � **mute** - Silence Notifications (Keep Monitoring)
Silences alerts but continues monitoring in background.

```bash
curl -X POST -d '{"action":"mute"}' https://.../<token>
```

**Response:**
```json
{"status":"muted","alarm_active":true,"position_notified":true,"message":"Notifications muted. Alarm still monitoring."}
```

**Behavior:**
- Silences movement notifications
- Continues monitoring in background
- Sets `position_notified = true` (prevents repeated alerts)

**State transitions:**
- Stays in current state
- `alarm_triggered` → effectively silenced (no more notifications)

**Use case:** You've been notified and want to check the situation without receiving repeated alerts.

#### 🔔 **unmute** - Re-enable Notifications
Re-enables notifications after `mute`.

```bash
curl -X POST -d '{"action":"unmute"}' https://.../<token>
```

**Response:**
```json
{"status":"unmuted","alarm_active":true,"position_notified":false,"message":"Notifications re-enabled."}
```

**Behavior:**
- Re-enables movement notifications
- Resets `position_notified = false`
- Allows new alerts to be sent

**State transitions:**
- `alarm_triggered` → `parked` (ready to detect movement again)

### Quick Reference Table

| Action | Effect | Alarm Active | Saves Position | Sends Notification | State Transition |
|--------|--------|--------------|----------------|-------------------|------------------|
| `start` | Enable monitoring | ✅ Yes | ⚠️ If GPS fresh | ✅ "Monitoring activated" | → `awaiting_position` or `parked` |
| `save` | Save current position | (unchanged) | ✅ Always | ✅ "Position saved" | → `position_saved` (if alarm off) |
| `stop` | Disable monitoring | ❌ No | ❌ No | ❌ Silent | → `position_saved` or `unknown` |
| `mute` | Silence alerts only | ✅ Yes | ❌ No | ❌ No | Stays in current state |
| `unmute` | Re-enable alerts | ✅ Yes | ❌ No | ❌ No | `alarm_triggered` → `parked` |

---

### Notification Messages

The integration sends **context-specific notifications** (localized based on your Home Assistant language):

| Event | Notification | Content |
|-------|-------------|---------|
| Position saved (`save` action) | 📍 Position saved | "Parking position saved." + map link |
| Monitoring started (`start` action) | 🟢 Monitoring activated | "Alarm active. Monitoring current position." + map link |
| Movement detected | 🚨 Vehicle moved! | Distance + saved position link + current position link |
| Alarm disabled (`stop` action) | — | No notification (silent) |

**Example movement notification:**
```
🚨 Vehicle moved!

⚠️ Detected movement of 250m from saved position!

📍 Saved position:
https://maps.google.com/?q=45.507,9.249

📍 Current position:
https://maps.google.com/?q=45.510,9.252
```

---

## Services
Services are exposed under the domain `vehicle_bt_parking_sentinel`:

- **`start`** — Enable alarm monitoring. Saves current `device_tracker` position (if GPS is fresh) and activates monitoring. Accepts optional `notify_waiting: true` parameter to send a notification if waiting for fresh GPS position.
- **`stop`** — Disable alarm monitoring completely (same as webhook `stop` action).
- **`save_position`** — Force-save the current tracker position (always, regardless of GPS timestamp) without changing alarm state.
- **`reset_flags`** — Reset notification flags (`position_notified = False`) to allow movement notifications again.
- **`clear_persisted`** — Full reset: clear saved coordinates, reset flags, disable alarm (returns to `unknown` state).
- **`get_webhook_info`** — Return webhook URL and token info for the entry.
- **`mute_notifications`** — Silence notifications but keep monitoring active (sets `position_notified = True`).
- **`unmute_notifications`** — Re-enable notifications (sets `position_notified = False`).

### Service Examples

**Activate monitoring (silent mode for automations):**
```yaml
service: vehicle_bt_parking_sentinel.start
data: {}
```

**Activate monitoring with feedback (for manual UI buttons):**
```yaml
service: vehicle_bt_parking_sentinel.start
data:
  notify_waiting: true  # Get notified if waiting for GPS
```

**Stop monitoring:**
```yaml
service: vehicle_bt_parking_sentinel.stop
data: {}
```

**Save position without enabling alarm:**
```yaml
service: vehicle_bt_parking_sentinel.save_position
data: {}
```

**Reset everything (for testing):**
```yaml
service: vehicle_bt_parking_sentinel.clear_persisted
data: {}
```

**Silence current alarm:**
```yaml
service: vehicle_bt_parking_sentinel.mute_notifications
data: {}
```

---

## Understanding State Behavior

### Start with Fresh vs Stale GPS

When you activate monitoring (via `start` webhook or `start` service):

**If GPS timestamp is fresh** (newer than activation time):
- ✅ Position saved immediately
- ✅ Alarm activated
- ✅ State becomes `parked`
- ✅ Notification "🟢 Monitoring activated" sent
- ✅ Monitoring starts immediately

**If GPS timestamp is stale** (older than activation time):
- ⚠️ Position NOT saved yet
- ✅ Alarm activated
- ⏳ State becomes `awaiting_position`
- ⏳ Flag `awaiting_activation_save = true` is set
- ⏳ Waits for next GPS update to save position
- ❌ No notification sent yet

**Why this matters in manual mode:**
- Parked vehicle may not move for hours
- GPS won't update until device moves or reconnects
- `start` alone → alarm active but no reference position!
- **Solution**: Always use `save` before `start` in manual mode

**Check status in sensor attributes:**
```yaml
sensor.vehicle_status:
  state: "awaiting_position"  # Waiting for GPS
  alarm_active: true  # Alarm enabled
  awaiting_activation_save: true  # Internal flag
  saved_latitude: null  # Position not saved yet!
  saved_longitude: null
```

**What happens next:**
- When device_tracker reports new GPS → position automatically saved
- State changes to `parked`
- Notification "🟢 Monitoring activated" sent
- Monitoring begins

### Immediate State Updates

After saving a position or changing alarm state, the sensor updates **immediately** (no delay). This is achieved through:

1. **Dispatcher signal**: `async_dispatcher_send` notifies sensor of changes
2. **Instant UI refresh**: State visible in UI within milliseconds
3. **No polling delay**: Does not wait for next Home Assistant update cycle

**Before this improvement (old behavior):**
- Position saved → 10-15 second delay before UI updates
- User had to wait to see state change from `awaiting_position` to `parked`

**Current behavior:**
- Position saved → UI updates instantly
- State changes immediately visible in Lovelace/frontend

### Resetting and Re-activating

**Start while already active:**
- Calling `start` when alarm is already active will RESET the search
- Clears `awaiting_activation_save` flag
- Re-checks for fresh GPS
- Useful for re-trying position save after GPS updates

**Example scenario:**
1. Called `start` but GPS was stale → state is `awaiting_position`
2. Wait a few seconds for GPS update
3. Call `start` again → resets search, finds fresh GPS, saves position
4. State becomes `parked` immediately

---## Best Practices and Common Use Cases

### Recommended Settings by Use Case

#### 🛵 **Scooter/Motorcycle Parking** (Recommended: `combined` mode)
```yaml
activation_mode: combined
stationary_minutes: 5
stationary_count: 2
tolerance_radius: 50
```
**Why**: Prevents false alarms from brief stops at traffic lights. Requires both disconnect AND stationary confirmation.

#### 🚗 **Car with Frequent Short Stops** (Recommended: `position` mode)
```yaml
activation_mode: position
stationary_minutes: 10
stationary_count: 3
tolerance_radius: 100
```
**Why**: Uses GPS position stability to confirm parking. Good for urban areas with many short stops.

#### 🚲 **Bicycle/E-Bike** (Recommended: `manual` mode)
```yaml
activation_mode: manual
tolerance_radius: 30
```
**Why**: Full control via button/automation. Activate only when you actually lock the bike.

**Example automation for manual mode**:
```yaml
automation:
  - alias: "Bike Parked - Activate Sentinel"
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: bike_parked
    action:
      - service: vehicle_bt_parking_sentinel.start
        data:
          notify_waiting: true
```

#### 🏍️ **Remote Parking (Garage/Storage)** (Recommended: `connection` mode)
```yaml
activation_mode: connection
tolerance_radius: 200
```
**Why**: Fast activation when BT disconnects. Good for garage parking where you don't move the vehicle after disconnect.

### Troubleshooting Common Scenarios

#### Scenario 1: "Sentinel saves position at traffic lights"
**Solution**: Switch from `connection` to `combined` or `position` mode with higher `stationary_count`:
```yaml
activation_mode: combined
stationary_minutes: 5
stationary_count: 3
```

#### Scenario 2: "Notification sent even when I'm just starting the vehicle"
**Solution**: Increase `tolerance_radius` or disable alarm when entering vehicle:
```yaml
automation:
  - alias: "Disable Alarm When Vehicle Started"
    trigger:
      - platform: state
        entity_id: device_tracker.smarttag
        to: "connected"
    action:
      - service: vehicle_bt_parking_sentinel.toggle_alarm
```

#### Scenario 3: "GPS position is stale when I activate manually"
**Behavior**: The integration sets `_awaiting_activation_save = true` and waits for fresh GPS.

**Check status**:
```yaml
sensor.vehicle_status attributes:
  awaiting_activation_save: true  # Waiting for fresh GPS
  alarm_active: true  # Alarm enabled but position not saved yet
```

**Solution**: Wait a few seconds for the device_tracker to report fresh GPS, or move slightly to trigger a GPS update.

#### Scenario 4: "Need to reset everything after testing"
**Solution**: Use `clear_persisted` service:
```yaml
service: vehicle_bt_parking_sentinel.clear_persisted
```
This clears saved position, disables alarm, and resets all flags.

### Advanced Automations

#### Send Custom Notification on Movement
```yaml
automation:
  - alias: "Vehicle Moved - Custom Alert"
    trigger:
      - platform: state
        entity_id: sensor.vehicle_status
        to: "alarm_triggered"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Vehicle Alert!"
          message: "Your vehicle has moved from parking location!"
          data:
            actions:
              - action: "open_map"
                title: "Open Map"
              - action: "disable_alarm"
                title: "Disable Alarm"
```

#### Activate Monitoring Only at Specific Locations
```yaml
automation:
  - alias: "Auto-Activate Sentinel at Work Parking"
    trigger:
      - platform: zone
        entity_id: device_tracker.smarttag
        zone: zone.work
        event: enter
    condition:
      - condition: state
        entity_id: device_tracker.smarttag
        state: "disconnected"
    action:
      - service: vehicle_bt_parking_sentinel.start
        data:
          notify_waiting: true
```


## Lovelace and cards

- The sensor entity `sensor.<entry_id>_vehicle_status` exposes attributes such as `saved_latitude`, `saved_longitude`, `saved_gpsUtcDt`, `saved_location_type`, `saved_last_seen`, `stationary_counter`, `alarm_active`.
- Examples included:
  - `examples/ui-lovelace.yaml` — basic YAML snippet.
  - `custom_components/.../www/vehicle-bt-parking-sentinel-card-v2.js` — minimal custom card.
  - `examples/button-card-stylized.yaml` — styled `custom:button-card` example.

To use the included custom card:

1. Register the resource in Home Assistant: Settings → Dashboards → Resources → Add resource
   - Resource: `/local/vehicle_bt_parking_sentinel/vehicle-bt-parking-sentinel-card-v2.js`
   - Type: `module`
2. Add a manual card with:

```yaml
type: custom:vehicle-bt-parking-sentinel-card
entity: sensor.<your_entry_id>_vehicle_status
title: Vehicle Parking
```

If you prefer not to use custom cards, the YAML examples or `custom:button-card` are viable alternatives (the latter requires `button-card` to be installed).

## Debugging and Logging

### Enable Debug Mode
1. Via Integration Options: Settings → Devices & Services → Vehicle BT Parking Sentinel → Configure → Enable debug mode
2. Via `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.vehicle_bt_parking_sentinel: debug
```

### View Logs
- **File**: `home-assistant.log` in your HA config directory
- **UI**: Settings → System → Logs

### Useful Log Searches
Look for keywords:
- `awaiting_activation_save` - Check if waiting for fresh GPS
- `Saved parking position` - Confirms position was saved
- `Alarm active changed` - Tracks alarm state transitions
- `Using coordinator from hass.data` - Webhook coordinator selection

### Quick Tests (Developer Tools → Services)

**Test activation (silent mode):**
```yaml
service: vehicle_bt_parking_sentinel.start
```

**Test activation (with feedback):**
```yaml
service: vehicle_bt_parking_sentinel.start
data:
  notify_waiting: true
```

**Reset everything:**
```yaml
service: vehicle_bt_parking_sentinel.clear_persisted
```

**Check sensor state:**
Go to Developer Tools → States → search for `sensor.vehicle_bt_parking_sentinel`

---## Installation and local testing

1. Copy `custom_components/vehicle_bt_parking_sentinel` into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. Add the integration from Settings → Devices & Services → Add Integration and follow the setup wizard.

Run unit tests locally for development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r dev-requirements.txt
pytest -q
```

## Contributing

PRs welcome. If you'd like to distribute the card via HACS, we can prepare a separate repository scaffold for the UI component.

---
If you'd like, I can add screenshots, an English/Italian split, or a short Quick Start section. Tell me what you prefer.

## Translations

This integration includes runtime translations for user-facing notifications and titles. Translation files live under `custom_components/vehicle_bt_parking_sentinel/translations/` and follow Home Assistant's localization format.

Included locales:

- `en` (English)
- `it` (Italian)
- `fr` (French)
- `de` (German)
- `ru` (Russian)
- `uk` (Ukrainian)
- `zh` (Chinese)

Message keys available under `component.messages`:

- `moved_title` — short title for movement notifications (e.g. "🚨 Vehicle moved!").
- `moved_message` — detailed movement message; supports `{lat}` and `{lon}` formatting placeholders.
- `saved_position_title` — title used when a parking position is saved.
- `alarm_disabled` — acknowledgement text when alarm is disabled via notification action.
- `vehicle_tracker_title` — generic notifier title used in some ack messages.
- `open_map_title` — title used when sending a map link via notification.

To add or update translations, add (or edit) `translations/<lang>.json` and include the `component.messages` object with the keys above. Keep placeholders `{lat}` and `{lon}` if you want the URL inserted automatically.

Example `translations/en.json` snippet:

```json
{
  "component": {
    "messages": {
      "moved_title": "🚨 Vehicle moved!",
      "moved_message": "The vehicle has moved! Open: https://maps.google.com/?q={lat},{lon}"
    }
  }
}
```

If you want, I can help refine translations or add additional locales.
