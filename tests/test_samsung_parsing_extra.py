"""Additional tests for Samsung parser edge cases and variants.
"""

from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.tag_guard_vehicle import utils


BASE_SAMPLE = {
    "ops": [
        {
            "oprnCrtDate": "20250101120000",
            "oprnDoneDate": "20250101120000",
            "oprnType": "LOCATION",
            "oprnStsCd": "2800",
            "oprnResultCode": "1200",
            "extra": {"gpsUtcDt": "20250101120000"},
            "latitude": "45.1234567",
            "longitude": "9.1234567",
        },
        {
            "oprnCrtDate": "20250101120000",
            "oprnDoneDate": "20250101120000",
            "oprnType": "CHECK_CONNECTION",
            "oprnStsCd": "2800",
            "oprnResultCode": "1200",
            "battery": "FULL",
        },
    ]
}


# Test: parser correctly preserves operation order and reads battery fields
def test_battery_and_op_types_and_order():
    ops = utils.parse_ops(BASE_SAMPLE["ops"])
    assert ops[0]["oprnType"] == "LOCATION"
    assert ops[1]["oprnType"] == "CHECK_CONNECTION"
    assert ops[1].get("battery") == "FULL"

# Test: parser provides gpsUtcDt which can be parsed into a UTC datetime
def test_gpsutc_datetime_parsing():
    ops = utils.parse_ops(BASE_SAMPLE["ops"])
    loc = ops[0]
    gpsdt = utils.safe_get(loc, "extra", "gpsUtcDt")
    # gpsUtcDt format is YYYYMMDDhhmmss -> convert to datetime
    parsed = datetime.strptime(gpsdt, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    assert parsed.year == 2025 and parsed.month == 1 and parsed.day == 1
    assert parsed.hour == 12 and parsed.minute == 0

# Test: parse_ops accepts a JSON string and returns a list of ops
def test_parse_ops_from_json_string():
    import json

    s = json.dumps(BASE_SAMPLE["ops"])
    parsed = utils.parse_ops(s)
    assert isinstance(parsed, list)
    assert parsed[0]["oprnType"] == "LOCATION"

