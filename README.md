# Tag Guard Vehicle

Home Assistant integration to monitor and protect your vehicle using a Bluetooth tracker (SmartTag, AirTag, Tile, etc.). 

## How It Works

**Never forget where you parked again, and get alerted if your vehicle is stolen or moved without permission.**

1. **🅿️ Automatic Position Saving** - When you park your vehicle, the integration automatically saves the GPS coordinates from your Bluetooth tracker
2. **🔐 Guard Activation** - After saving the position, monitoring is automatically activated (or manually, depending on your configuration)
3. **📍 Always Know Where You Parked** - The parking location is saved in the sensor attributes, so you can always find your vehicle
4. **🚨 Theft/Movement Detection** - If your vehicle moves beyond the configured radius (default 200m), you receive an immediate notification
5. **💾 Persistent Storage** - Your parking location is saved across Home Assistant restarts

**Use Cases:**
- 🚗 **Anti-theft protection** - Get notified if your car is being stolen or towed
- 🏍️ **Motorcycle/bike security** - Monitor your two-wheeler in public parking
- 🚐 **RV/camper tracking** - Know if your recreational vehicle moves from the campsite
- 🅿️ **Never forget parking location** - Always know where you left your vehicle

## Features

- 🚗 **Automatic parking detection** - Monitors your Bluetooth tracker and saves parking location
- 📍 **Movement detection** - Alerts you if your vehicle moves beyond a set radius
- 🔔 **Smart notifications** - Customizable alerts via Home Assistant notify service
- 🌐 **Webhook control** - Remote control via POST/GET requests
- 🎯 **Multiple activation modes** - Choose how and when to activate monitoring
- 🌍 **Multi-language support** - English, Italian, French, German, Russian, Ukrainian, Chinese

## Supported Devices

Currently, the integration supports **Samsung SmartTag 2** devices connected via:
- [HA-SmartThings-Find](https://github.com/Vedeneb/HA-SmartThings-Find) - Original integration
- [HA-SmartThings-Find (tomskra fork)](https://github.com/tomskra/HA-SmartThings-Find) - Fixed login issues

You need one of these integrations installed to provide the `device_tracker` entity for your SmartTag.

**Note:** Support for other Bluetooth trackers (AirTag, Tile, etc.) may be added in future releases.

## Installation

1. **Install SmartThings Find integration first:**
   - Install either [Vedeneb's](https://github.com/Vedeneb/HA-SmartThings-Find) or [tomskra's fork](https://github.com/tomskra/HA-SmartThings-Find) (recommended for login fix)
   - Configure your Samsung account
   - Verify your SmartTag appears as a `device_tracker` entity

2. **Install Tag Guard Vehicle:**
   - Copy `custom_components/tag_guard_vehicle` to your `<config>/custom_components/` folder
   - Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Tag Guard Vehicle"
3. Configure:
   - **Device Tracker**: Your Bluetooth tag entity (e.g., `device_tracker.smarttag`)
   - **Activation Mode**: How to detect parking (see below)
   - **Notify Service**: Home Assistant notification service to use
   - **Tolerance Radius**: Distance in meters before triggering alert (default: 200m)

### Activation Modes

- **`connection`** - Activates when Bluetooth disconnects (fastest)
- **`position`** - Activates when position is stable for X minutes (most accurate)
- **`combined`** - Requires both disconnect AND stable position (recommended)
- **`manual`** - Only activates via service call or webhook

## Usage

### Sensor State
The integration creates a sensor: `sensor.tag_guard_vehicle_<id>`

States:
- `position_saved` - Position saved, alarm disabled
- `parked` - Position saved, alarm enabled (monitoring)
- `alarm_triggered` - Vehicle has moved!
- `awaiting_position` - Waiting for fresh GPS data
- `unknown` - Initial state

### Services

#### Start Monitoring
```yaml
service: tag_guard_vehicle.start
data:
  notify_waiting: true  # Optional: notify if waiting for GPS
```

#### Stop Monitoring
```yaml
service: tag_guard_vehicle.stop
```

#### Save Current Position
```yaml
service: tag_guard_vehicle.save_position
```

#### Mute/Unmute Notifications
```yaml
service: tag_guard_vehicle.mute_notifications
# or
service: tag_guard_vehicle.unmute_notifications
```

### Webhook Control

After setup, you get a webhook URL for remote control:
```
https://your-ha-instance.com/api/webhook/<your-token>
```

**POST Actions:**
```bash
# Start monitoring
curl -X POST https://your-ha/api/webhook/TOKEN -H "Content-Type: application/json" -d '{"action": "start"}'

# Stop monitoring  
curl -X POST https://your-ha/api/webhook/TOKEN -H "Content-Type: application/json" -d '{"action": "stop"}'

# Save position
curl -X POST https://your-ha/api/webhook/TOKEN -H "Content-Type: application/json" -d '{"action": "save"}'
```

**GET Interface:**
Open the webhook URL in a browser to access a simple control page with buttons.

## Example Automations

### Activate on Button Press
```yaml
automation:
  - alias: "Start Vehicle Guard"
    trigger:
      - platform: state
        entity_id: input_button.park_car
    action:
      - service: tag_guard_vehicle.start
```

### Activate via Mobile Notification
```yaml
automation:
  - alias: "Ask to Enable Guard When Parking"
    trigger:
      - platform: state
        entity_id: device_tracker.my_smarttag
        to: "not_home"
    action:
      - service: notify.mobile_app
        data:
          message: "Enable vehicle guard?"
          data:
            actions:
              - action: "START_GUARD"
                title: "Enable"

  - alias: "Enable on Mobile Action"
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: "START_GUARD"
    action:
      - service: tag_guard_vehicle.start
```

### Stop Guard When Home
```yaml
automation:
  - alias: "Disable Guard When Home"
    trigger:
      - platform: state
        entity_id: person.me
        to: "home"
    condition:
      - condition: state
        entity_id: sensor.tag_guard_vehicle
        state: "parked"
    action:
      - service: tag_guard_vehicle.stop
```

## Lovelace Card

Simple status card:
```yaml
type: entities
entities:
  - entity: sensor.tag_guard_vehicle
    name: Vehicle Status
  - type: attribute
    entity: sensor.tag_guard_vehicle
    attribute: alarm_active
    name: Alarm
  - type: attribute
    entity: sensor.tag_guard_vehicle
    attribute: saved_position
    name: Parking Location
```

With control buttons:
```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: sensor.tag_guard_vehicle
  
  - type: horizontal-stack
    cards:
      - type: button
        name: Start
        icon: mdi:shield-check
        tap_action:
          action: call-service
          service: tag_guard_vehicle.start
      
      - type: button
        name: Stop
        icon: mdi:shield-off
        tap_action:
          action: call-service
          service: tag_guard_vehicle.stop
      
      - type: button
        name: Save Position
        icon: mdi:map-marker
        tap_action:
          action: call-service
          service: tag_guard_vehicle.save_position
```

## Troubleshooting

### No notifications received
1. Check your notify service is working: `service: notify.mobile_app` (test it)
2. Verify `alarm_active: true` in sensor attributes
3. Check notification is not muted (`position_notified: false`)
4. Enable debug logging (see below)

### GPS position not saving
1. Check `device_tracker` has valid GPS coordinates
2. Verify GPS timestamp is recent (< 10 minutes old)
3. For `position` mode: ensure vehicle is stationary for configured minutes
4. Use `notify_waiting: true` with start service to get status updates

### Debug Logging
Enable detailed logs:
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.tag_guard_vehicle: debug
```

Or via integration options: **Configure** → **Enable debug mode**

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `device_tracker` | Your Bluetooth tracker entity | Required |
| `activation_mode` | When to activate: `connection`, `position`, `combined`, `manual` | `combined` |
| `notifier` | Home Assistant notify service | `notify.notify` |
| `tolerance_radius_m` | Alert distance in meters | `200` |
| `stationary_minutes` | Minutes stable before activation (position/combined modes) | `3` |
| `stationary_count` | GPS readings required (position/combined modes) | `2` |
| `debug_mode` | Enable verbose logging | `false` |

## Advanced Features

### Samsung SmartTag Integration
The integration can parse Samsung SmartThings webhook payloads automatically. Configure your SmartTag to send webhooks to the Tag Guard Vehicle webhook URL.

### State Persistence
Position and alarm state persist across Home Assistant restarts.

### Multiple Vehicles
Install multiple instances of the integration for multiple vehicles - each gets its own sensor and webhook.

## Contributing

Issues and pull requests welcome at: https://github.com/metagliatore/tag-guard-vehicle

## License

MIT License - see repository for details
