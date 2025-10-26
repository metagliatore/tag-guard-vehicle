"""Test that the Lovelace card properly uses localization helpers.

Checks that:
`custom_components/vehicle_bt_parking_sentinel/www/vehicle-bt-parking-sentinel-card-v2.js`
includes code to localize labels via `hass.localize()` and falls back
to English if localization keys are missing.
"""

from pathlib import Path


JS_PATH = Path(__file__).parent.parent / "custom_components" / "vehicle_bt_parking_sentinel" / "www" / "vehicle-bt-parking-sentinel-card-v2.js"


def test_card_js_has_localize_keys():
    assert JS_PATH.exists(), f"JS card not found at {JS_PATH}"
    text = JS_PATH.read_text(encoding="utf-8")

    keys = [
        'component.vehicle_bt_parking_sentinel.messages.saved_coords_label',
        'component.vehicle_bt_parking_sentinel.messages.gps_utc_label',
        'component.vehicle_bt_parking_sentinel.messages.location_type_label',
        'component.vehicle_bt_parking_sentinel.messages.last_seen_label',
        'component.vehicle_bt_parking_sentinel.messages.stationary_counter_label',
        'component.vehicle_bt_parking_sentinel.messages.alarm_label',
        'component.vehicle_bt_parking_sentinel.messages.device_tracker_help',
    ]

    for key in keys:
        # allow either single or double quotes in the JS source
        assert f"localize('{key}')" in text or f'localize("{key}")' in text, f"missing localize call for {key}"


def test_card_js_has_english_fallbacks():
    text = JS_PATH.read_text(encoding="utf-8")
    fallbacks = [
        'Saved coords',
        'gpsUtcDt',
        'locationType',
        'last_seen',
        'stationary counter',
        'alarm',
        'Tracker',
        'Entity',
    ]

    for fb in fallbacks:
        assert fb in text, f"fallback string '{fb}' not found in card JS"

