"""Test clear_persisted service resets coordinator persisted fields and calls async_save."""
import asyncio

from custom_components.tag_guard_vehicle.services import async_register_services


class FakeHass:
    def __init__(self):
        self.services = self
        self._states = {}
        self._registered = None
        self._last_call = None
        self._registry = {}

    class S:
        def __init__(self, m):
            self.m = m

        def get(self, k):
            return self.m.get(k)

    @property
    def states(self):
        return FakeHass.S(self._states)

    def async_register(self, domain, name, func):
        # store by domain/name so tests can invoke a specific service
        self._registry[(domain, name)] = func
        # also keep last-registered for backward compatibility
        self._registered = func

    async def async_call(self, domain, service, data):
        # record calls (e.g., notify)
        self._last_call = (domain, service, data)
        return None


class DummyCoordinator:
    def __init__(self):
        self.saved_latitude = 1.1
        self.saved_longitude = 2.2
        self.saved_gpsUtcDt = "20250101000000"
        self.saved_location_type = "basic"
        self.saved_last_seen = "2025-01-01T00:00:00+00:00"
        self.position_notified = True
        self.last_tag_state = "connected"
        self.alarm_active = True
        self._saved = None

    async def async_save(self):
        # capture current saved state for assertion
        self._saved = {
            "saved_latitude": self.saved_latitude,
            "saved_longitude": self.saved_longitude,
            "saved_gpsUtcDt": self.saved_gpsUtcDt,
            "position_notified": self.position_notified,
            "last_tag_state": self.last_tag_state,
        }


def test_clear_persisted_service():
    hass = FakeHass()
    coord = DummyCoordinator()

    # register services
    asyncio.run(async_register_services(hass, coord, "device_tracker.x", None))

    # call the specific 'clear_persisted' service
    func = hass._registry.get(("tag_guard_vehicle", "clear_persisted"))

    class Call:
        def __init__(self):
            self.data = {}

    asyncio.run(func(Call()))

    # coordinator.async_save should have been called and coordinator fields cleared
    assert coord._saved is not None
    assert coord._saved["saved_latitude"] is None
    assert coord._saved["saved_longitude"] is None
    assert coord._saved["saved_gpsUtcDt"] is None
    assert coord._saved["position_notified"] is False
    assert coord._saved["last_tag_state"] is None
    # alarm should default to False after clear
    assert coord.alarm_active is False
