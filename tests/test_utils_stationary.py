"""Tests for stationary detection algorithms and counters."""

from custom_components.vehicle_bt_parking_sentinel.utils import update_stationary_counter, haversine_distance


# Test: new candidate is initialized and counter starts at 1
def test_update_stationary_counter_new_candidate():
    cand, cnt = update_stationary_counter(None, 0, (45.0, 9.0), 50)
    assert cand == (45.0, 9.0)
    assert cnt == 1


# Test: counter increments when movement is within tolerance
def test_update_stationary_counter_within_tolerance():
    base = (45.0, 9.0)
    new = (45.00009, 9.0)  # small move ~10 meters
    cand, cnt = update_stationary_counter(base, 2, new, 50)
    assert cand == base
    assert cnt == 3


# Test: counter resets and candidate updates when movement exceeds tolerance
def test_update_stationary_counter_outside_tolerance():
    base = (45.0, 9.0)
    new = (45.01, 9.0)  # ~1.1km
    cand, cnt = update_stationary_counter(base, 5, new, 50)
    assert cand == new
    assert cnt == 1


# Test: haversine_distance is symmetric when swapping points
def test_haversine_distance_symmetry():
    d1 = haversine_distance(45.0, 9.0, 45.001, 9.001)
    d2 = haversine_distance(45.001, 9.001, 45.0, 9.0)
    assert abs(d1 - d2) < 1e-6
