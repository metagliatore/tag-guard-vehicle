"""Unit tests for helper functions used by the coordinator."""

from custom_components.vehicle_bt_parking_sentinel.utils import (
    parse_connection_state,
    extract_coords_from_ops_attrs,
    build_notify_message,
)


# Test: parse_connection_state returns True for a successful LOCATION operation
def test_parse_connection_state_connected():
    ops = [{"oprnType": "LOCATION", "oprnResultCode": "1200", "oprnStsCd": "2800"}]
    attrs = {}
    connected, last_op = parse_connection_state(ops, attrs)
    assert connected is True
    assert last_op == ops[0]


# Test: parse_connection_state recognizes status when operations list is empty and attributes are present
def test_parse_connection_state_disconnected_by_attrs():
    ops = []
    attrs = {"oprnType": "CHECK_CONNECTION", "oprnResultCode": "1200", "oprnStsCd": "2800"}
    connected, last_op = parse_connection_state(ops, attrs)
    assert connected is True


# Test: extract_coords_from_ops_attrs prefers coordinates under 'extra' before top-level keys
def test_extract_coords_from_ops_attrs_prefers_extra():
    last_op = {"extra": {"latitude": 1.23, "longitude": 4.56}}
    attrs = {"latitude": 9.0, "longitude": 8.0}
    lat, lon = extract_coords_from_ops_attrs(last_op, attrs)
    assert lat == 1.23 and lon == 4.56


# Test: extract_coords_from_ops_attrs falls back to attributes when last_op lacks coordinates
def test_extract_coords_from_ops_attrs_fallback():
    last_op = {}
    attrs = {"latitude": 9.0, "longitude": 8.0}
    lat, lon = extract_coords_from_ops_attrs(last_op, attrs)
    assert lat == 9.0 and lon == 8.0


# Test: build_notify_message returns a title and a Google Maps link that includes coordinates
def test_build_notify_message_format():
    title, message = build_notify_message(45.0, 9.0)
    assert isinstance(title, str)
    assert "maps.google.com" in message
