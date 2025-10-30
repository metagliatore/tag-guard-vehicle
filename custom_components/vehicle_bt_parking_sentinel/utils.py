"""Utility functions for Vehicle BT Parking Sentinel."""
from .const import (
    CONF_DEVICE_TRACKER,
    CONF_PERSON_ENTITY,
    CONF_NOTIFIER,
    CONF_TOLERANCE_RADIUS,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
    CONF_ACTIVATION_MODE,
)

def meters_to_degrees(meters: float) -> float:
    """Convert meters to degrees roughly (1 deg lat ~ 111km)."""
    return meters / 111000.0


def has_moved(saved_lat: float | None, saved_lon: float | None, lat: float, lon: float, tolerance_m: float) -> bool:
    """Return True if the point (lat,lon) is further than tolerance_m from saved position.
    
    Returns:
        False if no saved position (cannot determine movement, avoid false alarms)
        False if within tolerance
        True if beyond tolerance
    """
    if saved_lat is None or saved_lon is None:
        # Cannot determine movement without saved position
        return False
    tol_deg = meters_to_degrees(tolerance_m)
    return (abs(lat - saved_lat) > tol_deg) or (abs(lon - saved_lon) > tol_deg)


def parse_ops(raw_ops):
    """Normalize ops field into a list of dicts.

    Accepts list, tuple, or JSON string. Returns empty list on parse errors.
    """
    if raw_ops is None:
        return []
    if isinstance(raw_ops, (list, tuple)):
        return list(raw_ops)
    if isinstance(raw_ops, str):
        try:
            import json

            parsed = json.loads(raw_ops)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return []
    try:
        return list(raw_ops)
    except Exception:
        return []


def safe_get(d, *keys, default=None):
    """Safely get nested keys from dict-like structures."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def validate_token(expected: str, provided: str) -> bool:
    """Compare tokens in constant-time fashion to avoid timing attacks (if possible)."""
    if expected is None:
        return True
    try:
        import hmac

        return hmac.compare_digest(str(expected), str(provided or ""))
    except Exception:
        return str(expected) == str(provided)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return Haversine distance between two points in meters.

    Uses the mean-earth radius approximation.
    """
    try:
        from math import radians, sin, cos, asin, sqrt

        rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
        dlat = rlat2 - rlat1
        dlon = rlon2 - rlon1
        a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        R = 6371000.0
        return R * c
    except Exception:
        # fallback: coarse degrees conversion
        return meters_to_degrees(abs(lat1 - lat2)) * 111000.0


def update_stationary_counter(stationary_candidate, stationary_counter, new_point, tolerance_m: float):
    """Update the stationary candidate and counter.

    stationary_candidate: tuple(lat, lon) or None
    stationary_counter: int
    new_point: tuple(lat, lon)
    tolerance_m: float - radius in meters

    Returns (candidate, counter).
    """
    # If no candidate yet, start one
    if stationary_candidate is None:
        return new_point, 1

    try:
        dist = haversine_distance(stationary_candidate[0], stationary_candidate[1], new_point[0], new_point[1])
    except Exception:
        # on error, reset candidate
        return new_point, 1

    if dist <= float(tolerance_m):
        return stationary_candidate, int(stationary_counter) + 1
    return new_point, 1


def parse_connection_state(ops, attrs):
    """Determine connection state from ops and attrs.

    Returns (connected: bool, last_op: dict).
    """
    last_op = {}
    if ops:
        try:
            last_op = ops[0] if isinstance(ops, (list, tuple)) and len(ops) > 0 else {}
        except Exception:
            last_op = {}

    def _safe_get(d, *keys, default=None):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k, default)
        return cur

    oprnType = last_op.get("oprnType") or _safe_get(attrs, "oprnType")
    oprnResultCode = last_op.get("oprnResultCode") or _safe_get(attrs, "oprnResultCode")
    oprnStsCd = last_op.get("oprnStsCd") or _safe_get(attrs, "oprnStsCd")

    connected = (
        str(oprnType) in ["LOCATION", "CHECK_CONNECTION"]
        and str(oprnResultCode) == "1200"
        and str(oprnStsCd) == "2800"
    )
    return connected, last_op


def extract_coords_from_ops_attrs(last_op, attrs):
    """Extract (lat, lon) from last_op or attrs with common fallbacks.

    Returns (lat, lon) or (None, None).
    """
    def _safe_get(d, *keys, default=None):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k, default)
        return cur

    lat = _safe_get(last_op, "extra", "latitude") or _safe_get(last_op, "latitude") or attrs.get("latitude")
    lon = _safe_get(last_op, "extra", "longitude") or _safe_get(last_op, "longitude") or attrs.get("longitude")
    return lat, lon


def parse_connection_state_by_model(tag_model: str | None, ops, attrs):
    """Model-aware parser: use registered parser when available.

    Falls back to the generic `parse_connection_state` implementation above.
    """
    try:
        from .parsers import get_parser

        if tag_model:
            p = get_parser(tag_model)
            if p and "parse_connection_state" in p:
                return p["parse_connection_state"](ops, attrs)
    except Exception:
        pass
    return parse_connection_state(ops, attrs)


def extract_coords_from_ops_attrs_by_model(tag_model: str | None, last_op, attrs):
    """Model-aware coord extraction using registered parser if present."""
    try:
        from .parsers import get_parser

        if tag_model:
            p = get_parser(tag_model)
            if p and "extract_coords_from_ops_attrs" in p:
                coords = p["extract_coords_from_ops_attrs"](last_op, attrs)
                try:
                    # Debug-friendly logging when running under HA
                    import logging

                    _LOG = logging.getLogger(__name__)
                    _LOG.debug("extract_coords_by_model(%s) returned %s for last_op=%s attrs_keys=%s", tag_model, coords, last_op, list(attrs.keys()) if isinstance(attrs, dict) else None)
                except Exception:
                    pass
                return coords
    except Exception:
        pass
    return extract_coords_from_ops_attrs(last_op, attrs)

# Backwards-compatible exports: prefer brand-specific parsers in `parsers/` package.
try:
    # prefer samsung parser when available
    from .parsers.samsung import parse_connection_state as _parse_connection_state, extract_coords_from_ops_attrs as _extract_coords_from_ops_attrs

    # override local definitions with parser implementations
    parse_connection_state = _parse_connection_state
    extract_coords_from_ops_attrs = _extract_coords_from_ops_attrs
except Exception:
    # keep the local implementations defined above
    pass


def build_notify_message(lat: float, lon: float):
    """Return (title, message) for a movement notification in English."""
    title = "🚨 Vehicle moved!"
    message = f"The vehicle has moved! Open: https://maps.google.com/?q={lat},{lon}"
    return title, message


async def translate(hass, key: str, default: str | None = None, **fmt) -> str:
    """Fetch a translated string for `component.messages.<key>` with fallback.

    key is a dotted path under `component` (e.g. 'messages.moved_message').
    If translation retrieval fails, return `default` or the final key.
    """
    try:
        from homeassistant.helpers.translation import async_get_translations

        translations = await async_get_translations(hass, __package__.split(".")[0])
        # translations is a dict keyed by language
        lang = getattr(hass.config, "language", None) or "en"
        comp = translations.get(lang, {}).get("component", {})
        node = comp
        for part in key.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
            if node is None:
                break
        text = node or default or key
        if fmt and isinstance(text, str):
            try:
                return text.format(**fmt)
            except Exception:
                return text
        return text
    except Exception:
        return default or key


async def async_build_notify_message(hass, lat: float, lon: float, saved_lat: float = None, saved_lon: float = None) -> tuple[str, str]:
    """Return translated (title, message) for movement notifications.

    Falls back to English defaults when translation keys are missing.
    
    Args:
        hass: Home Assistant instance
        lat: Current latitude
        lon: Current longitude
        saved_lat: Saved latitude (optional, for distance calculation)
        saved_lon: Saved longitude (optional, for distance calculation)
    
    Returns:
        Tuple of (title, message)
    """
    title = await translate(hass, "messages.moved_title", "🚨 Vehicle moved!")
    
    # Calculate distance if saved coordinates provided
    distance = 0
    if saved_lat is not None and saved_lon is not None:
        from .coordinator import haversine_distance
        distance = haversine_distance(saved_lat, saved_lon, lat, lon)
    
    # Build URLs
    current_url = f"https://maps.google.com/?q={lat},{lon}"
    saved_url = f"https://maps.google.com/?q={saved_lat},{saved_lon}" if saved_lat and saved_lon else current_url
    
    # Try new format first (with distance, saved_url, current_url)
    message = await translate(
        hass,
        "messages.moved_message",
        "⚠️ Detected movement of {distance}m from saved position!\n\n📍 Saved position:\n{saved_url}\n\n📍 Current position:\n{current_url}",
    )
    
    # Format with new placeholders
    try:
        message = message.format(
            distance=f"{distance:.0f}",
            saved_url=saved_url,
            current_url=current_url,
            lat=lat,  # Keep for backward compatibility
            lon=lon   # Keep for backward compatibility
        )
    except KeyError:
        # Fallback to old format if new placeholders not found
        message = message.format(lat=lat, lon=lon)
    
    return title, message


def should_finalize_combined(activation_mode: str, new_tag_state: str, stationary_counter: int, stationary_count: int) -> bool:
    """Return True if, under 'combined' activation, a disconnect should finalize save.

    For combined mode both a disconnect and sufficient stationary reports are required.
    """
    # Treat missing/None activation_mode as legacy 'connection' behaviour so
    # older installations that do not set the option still finalize on disconnect.
    mode = str(activation_mode) if activation_mode else "connection"
    # Only connection or combined modes may finalize on a disconnect.
    if mode not in ("connection", "combined"):
        return False
    # If activation is 'connection' we finalize on disconnect regardless of stationary counter.
    if mode == "connection":
        return new_tag_state == "disconnected"
    # for combined, require disconnect and at least stationary_count
    return new_tag_state == "disconnected" and int(stationary_counter) >= int(stationary_count)


def format_map_url(lat: float, lon: float) -> str:
    """Return a Google Maps URL for the coordinates."""
    return f"https://maps.google.com/?q={lat},{lon}"


def normalize_notification_action(action: str) -> str:
    """Normalize mobile notification action strings to uppercase keys."""
    if not action:
        return ""
    return str(action).strip().upper()


def needs_stationary_step(activation_mode: str) -> bool:
    """Return True if activation_mode requires stationary parameters.

    Activation modes that require stationary are 'position' and 'combined'.
    """
    return str(activation_mode) in ("position", "combined")


def build_create_payload(user_input: dict, base: dict | None = None) -> tuple[dict, dict]:
    """Build (data, options) payload for creating the config entry.

    base: existing user_data merged when stationary step completes.
    """
    import secrets

    base = base or {}
    activation = user_input.get(CONF_ACTIVATION_MODE) or base.get(CONF_ACTIVATION_MODE)
    token = user_input.get("webhook_token") or base.get("webhook_token") or secrets.token_urlsafe(16)
    data = {CONF_DEVICE_TRACKER: user_input.get(CONF_DEVICE_TRACKER) or base.get(CONF_DEVICE_TRACKER)}
    options = {
        CONF_PERSON_ENTITY: user_input.get(CONF_PERSON_ENTITY) or base.get(CONF_PERSON_ENTITY),
        CONF_NOTIFIER: user_input.get(CONF_NOTIFIER) or base.get(CONF_NOTIFIER),
        CONF_TOLERANCE_RADIUS: user_input.get(CONF_TOLERANCE_RADIUS) or base.get(CONF_TOLERANCE_RADIUS, 200),
        CONF_ACTIVATION_MODE: activation,
        "tag_model": user_input.get("tag_model") or base.get("tag_model"),
        "debug_mode": user_input.get("debug_mode", base.get("debug_mode", False)),
        "webhook_token": token,
    }
    # stationary values may be present in user_input
    if CONF_STATIONARY_MINUTES in user_input:
        options[CONF_STATIONARY_MINUTES] = int(user_input.get(CONF_STATIONARY_MINUTES))
    if CONF_STATIONARY_COUNT in user_input:
        options[CONF_STATIONARY_COUNT] = int(user_input.get(CONF_STATIONARY_COUNT))

    return data, options


def merge_options(existing: dict, user_input: dict) -> dict:
    """Merge existing options with user-provided ones for options flow.

    Returns the merged dict (user_input overrides existing).
    """
    return {**(existing or {}), **(user_input or {})}


def coerce_coords(lat, lon):
    """Attempt to convert lat/lon to floats; return (lat_f, lon_f) or (None, None)."""
    try:
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except Exception:
        return None, None


def should_save_after_stationary(candidate_lat, candidate_lon, current_lat, current_lon, tolerance_m: float) -> bool:
    """Return True if the distance between candidate and current is <= tolerance_m."""
    try:
        a = float(candidate_lat)
        b = float(candidate_lon)
        c = float(current_lat)
        d = float(current_lon)
    except Exception:
        return False
    dist = haversine_distance(a, b, c, d)
    return dist <= float(tolerance_m)
