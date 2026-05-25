"""Parser for Vedeneb/HA-SmartThings-Find payloads."""


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
