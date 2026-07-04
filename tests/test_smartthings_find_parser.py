"""Tests for SmartThings-Find by PixelShober parser compatibility."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.tag_guard_vehicle.parsers import get_parser
from custom_components.tag_guard_vehicle import utils


def _sample_attrs(d2d_status: str = "gattConnected"):
    return {
        "latitude": 45.1234567,
        "longitude": 9.1234567,
        "location_found": True,
        "update_success": True,
        "location_type": "TRACKER",
        "used_loc": {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
            "gps_accuracy": 14.249,
        },
        "raw_item": {
            "resultCode": "200",
            "geolocations": [
                {
                    "nearby": True,
                    "d2dStatus": d2d_status,
                    "latitude": "45.1234567",
                    "longitude": "9.1234567",
                    "method": "fused",
                    "accuracy": "14.249",
                    "lastUpdateTime": 1779729665244,
                    "valid": True,
                }
            ],
        },
        "last_seen": "2026-05-25T17:21:05.244000+00:00",
    }


def test_parser_registered_for_pixelshober_model():
    parser = get_parser("pixelshober_ha_smartthings_find")
    assert parser is not None
    assert "parse_connection_state" in parser
    assert "extract_coords_from_ops_attrs" in parser


def test_parse_connection_state_connected_from_d2d_status():
    attrs = _sample_attrs("gattConnected")
    connected, last_op = utils.parse_connection_state_by_model("pixelshober_ha_smartthings_find", [], attrs)

    assert connected is True
    assert last_op.get("latitude") in ("45.1234567", 45.1234567)


def test_parse_connection_state_disconnected_from_d2d_status():
    attrs = _sample_attrs("gattDisconnected")
    connected, _ = utils.parse_connection_state_by_model("pixelshober_ha_smartthings_find", [], attrs)

    assert connected is False


def test_extract_coords_from_new_payload_shape():
    attrs = _sample_attrs()
    connected, last_op = utils.parse_connection_state_by_model("pixelshober_ha_smartthings_find", [], attrs)
    lat, lon = utils.extract_coords_from_ops_attrs_by_model("pixelshober_ha_smartthings_find", last_op, attrs)

    assert connected is True
    assert float(lat) == 45.1234567
    assert float(lon) == 9.1234567


def test_parse_connection_state_network_only_tag_is_disconnected():
    """Tag seen only by the network (no nearby, no d2d) must be disconnected."""
    attrs = {
        "latitude": 45.1234000,
        "longitude": 9.1234000,
        "location_found": True,
        "update_success": True,
        "raw_item": {
            "resultCode": "200",
            "geolocations": [
                {
                    "latitude": "45.1234000",
                    "longitude": "9.1234000",
                    "method": "wifi",
                    "accuracy": "100.0",
                    "battery": "FULL",
                    "lastUpdateTime": 1783170442523,
                    "valid": True,
                }
            ],
        },
    }
    connected, _ = utils.parse_connection_state_by_model("pixelshober_ha_smartthings_find", [], attrs)
    assert connected is False


def test_parse_connection_state_nearby_phone_tag_is_connected():
    """Tag with nearby=True + gattConnected must be connected."""
    attrs = {
        "latitude": 45.1234568,
        "longitude": 9.1234568,
        "location_found": True,
        "update_success": True,
        "raw_item": {
            "resultCode": "200",
            "geolocations": [
                {
                    "nearby": True,
                    "d2dStatus": "gattConnected",
                    "latitude": "45.1234568",
                    "longitude": "9.1234568",
                    "method": "fused",
                    "accuracy": "14.003",
                    "battery": "FULL",
                    "lastUpdateTime": 1783173310335,
                    "valid": True,
                }
            ],
        },
    }
    connected, _ = utils.parse_connection_state_by_model("pixelshober_ha_smartthings_find", [], attrs)
    assert connected is True

