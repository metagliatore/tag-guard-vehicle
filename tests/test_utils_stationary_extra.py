"""Additional tests covering edge cases of stationary detection logic."""

from custom_components.tag_guard_vehicle.utils import coerce_coords, should_save_after_stationary


# Test: coerce_coords parses numeric strings into floats
def test_coerce_coords_valid():
    lat, lon = coerce_coords("45.0", "9.0")
    assert lat == 45.0 and lon == 9.0


# Test: coerce_coords returns (None, None) for invalid or missing inputs
def test_coerce_coords_invalid():
    lat, lon = coerce_coords(None, "9.0")
    assert lat is None and lon is None
    lat, lon = coerce_coords("abc", "9.0")
    assert lat is None and lon is None


# Test: should_save_after_stationary returns True for identical points within tolerance
def test_should_save_after_stationary_true():
    assert should_save_after_stationary(45.0, 9.0, 45.0, 9.0, 100)


# Test: should_save_after_stationary returns False for distant points
def test_should_save_after_stationary_false():
    assert not should_save_after_stationary(45.0, 9.0, 46.0, 9.0, 100)
