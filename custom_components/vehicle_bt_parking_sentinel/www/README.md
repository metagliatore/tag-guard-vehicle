# Vehicle BT Parking Sentinel — Lovelace Card

This file explains how to enable and use the minimal custom Lovelace card included with the integration.

## Automatic Registration (Recommended)

Starting from version X.X.X, the card is **automatically registered** when you install the integration. You don't need to manually add it to Resources!

Simply add the card to your dashboard:

1. Go to your dashboard
2. Click "Add Card"
3. Search for "Vehicle BT Parking Sentinel" in the card picker
4. Or add a Manual card with this YAML:

```yaml
type: custom:vehicle-bt-parking-sentinel-card
entity: sensor.<your_entry_id>_vehicle_status
title: Vehicle Parking
```

## Manual Registration (if auto-registration fails)

If the card doesn't appear or you see "Custom element doesn't exist", manually register it:

1. Go to **Settings** → **Dashboards** → **Resources** (top-right menu)
2. Click **Add Resource**
3. Set:
   - **URL**: `/vehicle_bt_parking_sentinel/vehicle-bt-parking-sentinel-card-v2.js`
   - **Type**: `JavaScript Module`
4. Click **Create**

**Alternative paths** (try these if the above doesn't work):
- `/hacsfiles/vehicle_bt_parking_sentinel/vehicle-bt-parking-sentinel-card-v2.js`
- `/local/community/vehicle_bt_parking_sentinel/vehicle-bt-parking-sentinel-card-v2.js`

## Card File Location

The card JavaScript file is located at:
```
custom_components/vehicle_bt_parking_sentinel/www/vehicle-bt-parking-sentinel-card-v2.js
```

Home Assistant automatically serves files from `custom_components/<domain>/www/` at the URL path `/<domain>/`.

## Using the Card
- Add a Manual card and paste this YAML, replacing `sensor.<your_entry_id>_vehicle_status` with your sensor entity id (Developer Tools → States):

```yaml
type: custom:vehicle-bt-parking-sentinel-card
entity: sensor.<your_entry_id>_vehicle_status
title: Vehicle Parking
```

Example with explicit entity attributes (useful in YAML views):

```yaml
- type: custom:vehicle-bt-parking-sentinel-card
  entity: sensor.12345678_vehicle_status
  title: Vehicle Parking
```

Customization
- `title`: the card title shown in the UI.
- The component is intentionally minimal and has no external JavaScript dependencies.

## Troubleshooting

### "Custom element doesn't exist: vehicle-bt-parking-sentinel-card"

1. **Check if resource is registered**: Go to Settings → Dashboards → Resources and verify the entry exists
2. **Try manual registration**: Use the URL `/vehicle_bt_parking_sentinel/vehicle-bt-parking-sentinel-card-v2.js` (see Manual Registration section above)
3. **Clear browser cache**: Hard-reload the dashboard (Ctrl+Shift+R or Cmd+Shift+R)
4. **Check browser console**: Press F12, go to Console tab, look for errors or the message "vehicle-bt-parking-sentinel-card loaded"
5. **Verify file exists**: Check that `custom_components/vehicle_bt_parking_sentinel/www/vehicle-bt-parking-sentinel-card-v2.js` exists in your HA config directory

### Card shows "Entity not found"

- Make sure you're using the correct entity ID. Check Developer Tools → States for entities starting with `sensor.` and containing `vehicle_status`
- The entity ID format is usually: `sensor.<entry_id>_vehicle_status`

### Card doesn't update in real-time

- This is normal - the card updates when the sensor state changes
- If the sensor isn't updating, check the integration logs (see main README for logging instructions)

### Testing the card is loaded

Open your browser console (F12) and run:
```javascript
customElements.get('vehicle-bt-parking-sentinel-card')
```

If it returns a class definition, the card is loaded. If it returns `undefined`, the resource isn't loaded properly.

HACS option (recommended for distribution)
- To distribute and keep the card updated for end users, consider publishing the card via HACS (requires a separate repository and JS packaging). I can help scaffold that if needed.

Developer notes
- The card reads the state and attributes from the specified entity. Make sure the integration creates the sensor and that it exposes attributes such as `saved_latitude`, `saved_longitude`, `saved_gpsUtcDt`, `saved_location_type`, `saved_last_seen`, `stationary_counter`, and `alarm_active`.

Webhook control page and examples

The integration exposes a webhook URL that can be used to trigger saves or control the sentinel. Visiting the webhook URL in a browser (GET) shows a small HTML control page with three buttons: Start, Stop, and Trigger Save.

- Webhook URL format:

  `https://<your-ha>/api/webhook/<token>`

- Browser (GET): opens the control page. The control page posts actions back to the same webhook URL.

- Actions supported (via POST JSON body or query parameter `action`):
  - `start` / `enable` / `arm` — enable the sentinel/alarm.
  - `stop` / `disable` / `disarm` — disable the sentinel/alarm.
  - `save` / `trigger` / `save_now` — trigger an immediate save using the configured `device_tracker` as the coordinate source.

Security: token usage
- The webhook token may be sent either by including it in the URL path (the usual HA webhook pattern) or by providing it as a header `X-Integration-Token` or query param `token` for convenience when using the control page.

Important behaviour notes
- The browser GET control page does not accept coordinates from query parameters. A `save` action triggered from the control page or via GET will always use the configured `device_tracker` entity to obtain coordinates (this prevents accidental use of untrusted query params).
- If you POST JSON to the webhook you may include `latitude` and `longitude` keys (or provide `ops` / tag attributes as used by some trackers) — otherwise the handler will fall back to the `device_tracker` entity.

Examples

- Trigger save using a POST with JSON coordinates:

```bash
curl -X POST "https://<your-ha>/api/webhook/<token>" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 45.12345, "longitude": 9.12345}'
```

- Trigger save using the device tracker fallback (no coords in payload):

```bash
curl -X POST "https://<your-ha>/api/webhook/<token>" \
  -H "Content-Type: application/json" \
  -d '{}'   # handler will use the configured device_tracker to get coordinates
```

- Start/stop the sentinel via POST action:

```bash
curl -X POST "https://<your-ha>/api/webhook/<token>" \
  -H "Content-Type: application/json" \
  -d '{"action": "start"}'

curl -X POST "https://<your-ha>/api/webhook/<token>" \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}'
```

- Use the browser control page (GET) and include the token in the URL for convenience:

  `https://<your-ha>/api/webhook/<token>?token=<token>`

Notes
- The root README already documents the main webhook usage; this file focuses on the Lovelace card and the lightweight control-page convenience for testing and local control.

Would you like me to also add a short `button-card` example here or move an English copy of the root README into the `www/` folder?
