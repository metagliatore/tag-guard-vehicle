"""Tests for save-on-activation behavior when enabling the monitoring."""
import asyncio

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeHass:
    def __init__(self, states_map=None):
        self.services = self
        self._states = states_map or {}

    class S:
        def __init__(self, m):
            self.m = m

        def get(self, k):
            return self.m.get(k)

    @property
    def states(self):
        return FakeHass.S(self._states)


class FakeState:
    def __init__(self, attrs: dict):
        self.attributes = attrs


class DummyStore:
    async def async_load(self):
        return None

    async def async_save(self, data):
        return None


async def _run_with_gps(gps_ts):
    attrs = {
        "latitude": '45.0',
        "longitude": '9.0',
        "ops": [{"extra": {"gpsUtcDt": gps_ts}, "latitude": '45.0', "longitude": '9.0'}],
    }
    hass = FakeHass(states_map={"device_tracker.test": FakeState(attrs)})
    coord = VehicleCoordinator(hass, "e2", {"device_tracker": "device_tracker.test", "activation_mode": "manual"})
    coord.store = DummyStore()
    # Ensure alarm is off initially
    coord.alarm_active = False
    # Enable with activation_time slightly before gps_ts
    await coord.set_alarm_active(True, activation_time="20251027204700")
    return coord


def test_activation_saves_when_gps_newer():
    # gpsUtcDt newer than activation_time -> should save
    coord = asyncio.run(_run_with_gps("20251027204800"))
    assert coord.saved_latitude is not None


def test_activation_does_not_save_when_gps_older():
    # gpsUtcDt older than activation_time -> should not save
    coord = asyncio.run(_run_with_gps("20251027204600"))
    assert coord.saved_latitude is None
