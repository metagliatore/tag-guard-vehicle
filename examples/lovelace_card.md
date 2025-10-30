# Lovelace Examples for Tag Guard Vehicle

This file contains YAML snippets you can copy to your Lovelace interface to display sensor state and add manual actions.

Replace `sensor.<your_entry_id>_vehicle_status` with the actual entity_id created by the integration (check Developer Tools → States).

---

## 1) Simple Entities Card

```yaml
type: entities
title: Vehicle Status
entities:
  - entity: sensor.<your_entry_id>_vehicle_status
    name: Parking guard
  - type: attribute
    entity: sensor.<your_entry_id>_vehicle_status
    attribute: saved_latitude
    name: Saved Latitude
  - type: attribute
    entity: sensor.<your_entry_id>_vehicle_status
    attribute: saved_longitude
    name: Saved Longitude
  - type: attribute
    entity: sensor.<your_entry_id>_vehicle_status
    attribute: stationary_counter
    name: Stationary Counter
  - type: attribute
    entity: sensor.<your_entry_id>_vehicle_status
    attribute: alarm_active
    name: Alarm Active
```

---

## 2) Markdown Card with Map Link and Status

```yaml
type: markdown
title: Vehicle - Quick View
content: |
  **Status:** {{ states('sensor.<your_entry_id>_vehicle_status') }}  
  **Saved Position:** {{ state_attr('sensor.<your_entry_id>_vehicle_status','saved_latitude') }},{{ state_attr('sensor.<your_entry_id>_vehicle_status','saved_longitude') }}  
  **Awaiting Confirmation:** {% if state_attr('sensor.<your_entry_id>_vehicle_status','stationary_counter')|int > 0 %}Yes ({{ state_attr('sensor.<your_entry_id>_vehicle_status','stationary_counter') }}){% else %}No{% endif %}  
  
  {% if state_attr('sensor.<your_entry_id>_vehicle_status','saved_latitude') and state_attr('sensor.<your_entry_id>_vehicle_status','saved_longitude') %}
  [Open in Google Maps](https://maps.google.com/?q={{ state_attr('sensor.<your_entry_id>_vehicle_status','saved_latitude') }},{{ state_attr('sensor.<your_entry_id>_vehicle_status','saved_longitude') }})
  {% endif %}
```

---

## 3) Advanced Example with Custom Button Card

If you use the `button-card` custom card (optional), this shows status and allows manual trigger:

```yaml
type: vertical-stack
cards:
  - type: 'custom:button-card'
    entity: sensor.<your_entry_id>_vehicle_status
    show_name: true
    name: Vehicle Status
    show_state: true
    icon: mdi:motorbike
    state:
      - value: 'parked'
        color: green
        icon: mdi:parking
      - value: 'awaiting_position'
        color: orange
        icon: mdi:timer-sand
      - value: 'alarm_triggered'
        color: red
        icon: mdi:alarm
  - type: horizontal-stack
    cards:
      - type: button
        name: Save Position (Manual)
        tap_action:
          action: call-service
          service: tag_guard_vehicle.manual_trigger
          data: {}
      - type: button
        name: Toggle Alarm
        tap_action:
          action: call-service
          service: tag_guard_vehicle.toggle_alarm
          data: {}
```

---

## Useful Notes
- The displayed `attributes` are populated by the coordinator: `stationary_candidate` and `stationary_counter` help you understand if position confirmation is in progress.
- `manual_trigger` service saves the current device_tracker position and enables monitoring. It does NOT accept custom coordinates for security reasons.
- If you want the card to show debug information, enable `debug_mode` in the integration options and enable logs for the component.
