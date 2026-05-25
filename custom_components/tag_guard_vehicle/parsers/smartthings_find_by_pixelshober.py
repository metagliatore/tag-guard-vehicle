"""Parser for PixelShober/HA-SmartThings-Find payloads."""


def _safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
    return cur


def _first_geolocation(attrs):
    raw_item = attrs.get("raw_item") if isinstance(attrs, dict) else None
    geolocations = _safe_get(raw_item, "geolocations")
    if isinstance(geolocations, (list, tuple)) and geolocations:
        first = geolocations[0]
        if isinstance(first, dict):
            return first
    return {}


def parse_connection_state(ops, attrs):
    """Determine connection state from SmartThings-Find attributes.

    Returns (connected: bool, last_op: dict).
    """
    attrs = attrs if isinstance(attrs, dict) else {}

    geolocation = _first_geolocation(attrs)
    d2d_status = str(geolocation.get("d2dStatus") or "").strip().lower()

    if d2d_status in {"gattconnected", "connected"}:
        connected = True
    elif d2d_status in {"gattdisconnected", "disconnected"}:
        connected = False
    else:
        nearby = geolocation.get("nearby")
        if nearby is not None:
            connected = bool(nearby)
        else:
            connected = bool(attrs.get("location_found") and attrs.get("update_success"))

    # keep a shape compatible with the rest of integration logging/metadata handling
    last_op = {
        "latitude": geolocation.get("latitude") or _safe_get(attrs, "used_loc", "latitude") or attrs.get("latitude"),
        "longitude": geolocation.get("longitude") or _safe_get(attrs, "used_loc", "longitude") or attrs.get("longitude"),
        "extra": {
            "gpsUtcDt": geolocation.get("lastUpdateTime") or attrs.get("gps_date") or attrs.get("last_seen"),
            "locationType": geolocation.get("method") or attrs.get("location_type") or attrs.get("locationType"),
        },
    }

    return connected, last_op


def extract_coords_from_ops_attrs(last_op, attrs):
    """Extract (lat, lon) from SmartThings-Find payload fields."""
    attrs = attrs if isinstance(attrs, dict) else {}
    last_op = last_op if isinstance(last_op, dict) else {}
    geolocation = _first_geolocation(attrs)

    lat = (
        _safe_get(last_op, "extra", "latitude")
        or _safe_get(last_op, "latitude")
        or _safe_get(attrs, "used_loc", "latitude")
        or geolocation.get("latitude")
        or attrs.get("latitude")
    )
    lon = (
        _safe_get(last_op, "extra", "longitude")
        or _safe_get(last_op, "longitude")
        or _safe_get(attrs, "used_loc", "longitude")
        or geolocation.get("longitude")
        or attrs.get("longitude")
    )

    return lat, lon
