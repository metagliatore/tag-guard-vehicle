"""Constants for the Tag Guard Vehicle integration."""

DOMAIN = "tag_guard_vehicle"

# Configuration constants
CONF_DEVICE_TRACKER = "device_tracker"
CONF_PERSON_ENTITY = "person_entity"
CONF_NOTIFIER = "notifier"
CONF_TOLERANCE_RADIUS = "tolerance_radius"
CONF_STATIONARY_MINUTES = "stationary_minutes"
CONF_STATIONARY_COUNT = "stationary_count"
CONF_ACTIVATION_MODE = "activation_mode"
CONF_TAG_MODEL = "tag_model"
CONF_DEBUG_MODE = "debug_mode"
CONF_WEBHOOK_TOKEN = "webhook_token"

DEFAULT_WEBHOOK_ID = "vehicle-save-location"

# Tag models
TAG_MODELS = {
    "vedeneb_ha_smartthings_find": "Vedeneb/HA-SmartThings-Find",
    "pixelshober_ha_smartthings_find": "SmartThings-Find by PixelShober",
}

# Note: keys in TAG_MODELS are intended to match parser registry keys in
# `parsers/__init__.py` (for example 'vedeneb_ha_smartthings_find'). Adding a new tag
# model typically requires adding a parser module under `parsers/` with the
# same key name.

# Activation modes supported by the integration. "manual" is a mode where the
# guard must be activated manually by the user (it is always available and
# does not require stationary parameters).
ACTIVATION_MODES = ["connection", "position", "combined", "manual"]
