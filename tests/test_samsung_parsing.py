"""Tests Samsung-specific parsing logic under the parsers package.

These ensure the integration correctly extracts coordinates and connection
state from Samsung tag payloads.
"""

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.tag_guard_vehicle import utils


SAMPLE = {
    "source_type": "gps",
    "battery_level": 100,
    "latitude": "45.1234567",
    "longitude": "9.1234567",
    "gps_accuracy": 20.1,
    "dev_name": "SmartTagScooter",
    "dev_id": 123456789,
    "update_success": True,
    "location_found": True,
    "ops": [
        {
            "oprnCrtDate": "20251026221803",
            "oprnDoneDate": "20251026221803",
            "oprnType": "LOCATION",
            "oprnStsCd": "2800",
            "oprnResultCode": "1200",
            "extra": {"gpsUtcDt": "20251026221714"},
            "latitude": "45.1234567",
            "longitude": "9.1234567",
            "horizontalUncertainty": "14.229",
            "verticalUncertainty": "14.229",
            "locationType": "basic",
        },
        {
            "oprnCrtDate": "20251026221803",
            "oprnDoneDate": "20251026221803",
            "oprnType": "CHECK_CONNECTION",
            "oprnStsCd": "2800",
            "oprnResultCode": "1200",
            "battery": "FULL",
        },
    ],
}


# Test: parse_ops returns a list and the first operation is a LOCATION with gpsUtcDt
def test_parse_ops_returns_list_and_extract_first_location():
    ops = utils.parse_ops(SAMPLE.get("ops"))
    assert isinstance(ops, list)
    first = ops[0]
    assert first.get("oprnType") == "LOCATION"
    lat = utils.safe_get(first, "extra", "gpsUtcDt")
    assert lat == "20251026221714"


# Test: parser-handled ops support replacing coordinates and computing haversine=0
def test_replace_coords_with_fake_values_and_distance():
    ops = utils.parse_ops(SAMPLE.get("ops"))
    first = ops[0]
    # replace coords with fake ones
    fake_lat = 10.0
    fake_lon = 20.0
    first["latitude"] = str(fake_lat)
    first["longitude"] = str(fake_lon)

    # ensure safe_get returns new coords
    lat_str = utils.safe_get(first, "latitude")
    lon_str = utils.safe_get(first, "longitude")
    assert lat_str == str(fake_lat)
    assert lon_str == str(fake_lon)

    # compute haversine between fake coords and themselves -> 0
    d = utils.haversine_distance(fake_lat, fake_lon, float(lat_str), float(lon_str))
    assert d == 0.0

