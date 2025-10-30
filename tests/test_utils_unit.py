"""General unit tests for small utility functions (haversine, parsing, tokens)."""

import math
import sys
from pathlib import Path

# make repository root importable so we can import the local custom_components
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.tag_guard_vehicle import utils


# Test: when saved position is None, has_moved should return False (cannot determine movement)
def test_meters_to_degrees_and_has_moved_none_saved():
    assert not utils.has_moved(None, None, 45.0, 9.0, 50)


# Test: has_moved returns False for coordinates within the movement tolerance
def test_meters_to_degrees_and_has_moved_close():
    saved_lat = 45.0
    saved_lon = 9.0
    lat = saved_lat + utils.meters_to_degrees(10) / 2
    lon = saved_lon
    assert not utils.has_moved(saved_lat, saved_lon, lat, lon, 10)


# Test: parse_ops accepts a list, JSON string, and returns [] for invalid input
def test_parse_ops_list_and_string_and_invalid():
    ops_list = [{"a": 1}, {"b": 2}]
    assert utils.parse_ops(ops_list) == ops_list

    ops_str = '[{"x": 1}, {"y": 2}]'
    parsed = utils.parse_ops(ops_str)
    assert isinstance(parsed, list) and parsed[0]["x"] == 1

    assert utils.parse_ops(None) == []
    assert utils.parse_ops('not a json') == []


# Test: safe_get retrieves nested keys and returns the provided default when missing
def test_safe_get_nested_and_default():
    d = {"a": {"b": {"c": 5}}}
    assert utils.safe_get(d, "a", "b", "c") == 5
    assert utils.safe_get(d, "a", "z", default=42) == 42


# Test: validate_token returns True for the correct token and False otherwise
def test_validate_token_compare_digest_and_fallback():
    token = "secret-token"
    assert utils.validate_token(token, "secret-token")
    assert not utils.validate_token(token, "wrong")


# Test: haversine_distance approximates ~111km per degree latitude
def test_haversine_distance_known():
    lat1, lon1 = 0.0, 0.0
    lat2, lon2 = 1.0, 0.0
    dist = utils.haversine_distance(lat1, lon1, lat2, lon2)
    assert 110000 < dist < 112000


# Test: haversine_distance returns 0.0 for identical coordinates
def test_haversine_distance_identical():
    assert utils.haversine_distance(45.0, 9.0, 45.0, 9.0) == 0.0
