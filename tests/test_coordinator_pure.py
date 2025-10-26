"""Unit tests for coordinator logic without Home Assistant integration.

These tests run coordinator algorithms as pure functions where possible.
"""

import pytest

from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
from custom_components.vehicle_bt_parking_sentinel.utils import haversine_distance


class DummyHass:
    def __init__(self):
        self.async_create_task = lambda coro: None
        self.states = DummyStates()


class DummyStates:
    def __init__(self):
        self._dict = {}

    def get(self, entity_id):
        return self._dict.get(entity_id)


class DummyStore:
    def __init__(self):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


def make_coordinator():
    hass = DummyHass()
    coord = VehicleCoordinator(hass, "test_entry", {})
    # replace store with dummy to avoid IO
    coord.store = DummyStore()
    return coord


# Verify has_moved returns False when no saved coordinates exist (cannot determine movement)
def test_has_moved_without_saved():
    c = make_coordinator()
    assert not c.has_moved(45.0, 9.0, 100)


# Verify has_moved returns False for same point and True for a far point
def test_has_moved_with_saved():
    c = make_coordinator()
    c.saved_latitude = 45.0
    c.saved_longitude = 9.0
    # same point -> not moved
    assert not c.has_moved(45.0, 9.0, 10)
    # far point -> moved
    assert c.has_moved(45.01, 9.0, 100)


@pytest.mark.asyncio
# Verify stationary check saves the current device_tracker coordinates
@pytest.mark.asyncio
async def test_stationary_check_saves(tmp_path, monkeypatch):
    c = make_coordinator()
    # set config device_tracker and tolerance
    c.config["device_tracker"] = "device.tracker_1"
    c.tolerance_radius = 100
    # simulate states
    class S:
        attributes = {"latitude": 45.0, "longitude": 9.0}

    c.hass.states._dict["device.tracker_1"] = S()

    # call stationary check which should save position
    await c._stationary_check(45.0, 9.0)
    assert c.saved_latitude == 45.0
    assert c.saved_longitude == 9.0
