"""Constants for the Vehicle BT Parking Sentinel integration."""

DOMAIN = "vehicle_bt_parking_sentinel"

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
    "samsung_smarttag2": "Samsung SmartTag2",
}

# Note: keys in TAG_MODELS are intended to match parser registry keys in
# `parsers/__init__.py` (for example 'samsung_smarttag2'). Adding a new tag
# model typically requires adding a parser module under `parsers/` with the
# same key name.

# Activation modes supported by the integration. "manual" is a mode where the
# sentinel must be activated manually by the user (it is always available and
# does not require stationary parameters).
ACTIVATION_MODES = ["connection", "position", "combined", "manual"]
