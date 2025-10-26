"""Scenario test: inject user's device_tracker state and verify manual_trigger saves coordinates."""
import asyncio

from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
from custom_components.vehicle_bt_parking_sentinel.services import async_register_services


class FakeHass:
    def __init__(self, states_map=None):
        self.services = self
        self._states = states_map or {}
        self._registered_services = {}  # Map (domain, name) -> func

    class S:
        def __init__(self, m):
            self.m = m

        def get(self, k):
            return self.m.get(k)

    @property
    def states(self):
        return FakeHass.S(self._states)

    def async_register(self, domain, name, func):
        self._registered_services[(domain, name)] = func
        # Keep backward compat for old tests
        self._registered = func

    async def async_call(self, domain, service, data):
        # no-op notify
        self._last_call = (domain, service, data)
        return None


class FakeState:
    def __init__(self, attrs: dict):
        self.attributes = attrs


async def run_scenario():
    # build the device_tracker state using the user's dump (latitude/longitude in attributes and ops)
    attrs = {
        "latitude": '45.1234567',
        "longitude": '9.1234567',
        "ops": [
            {
                "oprnCrtDate": '20251027204827',
                "oprnDoneDate": '20251027204827',
                "oprnType": 'LOCATION',
                "oprnStsCd": '2800',
                "oprnResultCode": '1200',
                "extra": {"gpsUtcDt": '20251027204505'},
                "latitude": '45.1234567',
                "longitude": '9.1234567',
            }
        ],
    }

    hass = FakeHass(states_map={"device_tracker.smarttagscooter": FakeState(attrs)})
    coord = VehicleCoordinator(hass, "entry1", {"device_tracker": "device_tracker.smarttagscooter", "activation_mode": "manual"})
    # replace store with dummy that does no IO
    class DummyStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            return None

    coord.store = DummyStore()

    # register services
    await async_register_services(hass, coord, "device_tracker.smarttagscooter", None)

    # Get the manual_trigger function
    func = hass._registered_services.get(("vehicle_bt_parking_sentinel", "manual_trigger"))

    class Call:
        def __init__(self, data=None):
            self.data = data or {}

    await func(Call())
    return coord


def test_manual_save_scenario():
    """Test manual_trigger with old GPS timestamp - should set awaiting flag."""
    coord = asyncio.run(run_scenario())
    # The GPS timestamp in the test data is old (20251027204505)
    # so manual_trigger should:
    # 1. Enable alarm
    assert coord.alarm_active is True
    # 2. Set awaiting flag (GPS too old to save immediately)
    assert getattr(coord, '_awaiting_activation_save', False) is True
    # 3. Position NOT saved yet (waiting for fresh GPS)
    # Note: The old implementation would save stale coords; new one waits
    # In a real scenario, when fresh GPS arrives via device_tracker event,
    # the position will be saved and awaiting flag cleared.


async def run_scenario_fresh_gps():
    """Scenario with fresh GPS timestamp."""
    from datetime import datetime, timedelta
    # Create a timestamp slightly in the future to ensure it's fresher than activation_time
    future_time = datetime.utcnow() + timedelta(seconds=5)
    fresh_ts = future_time.strftime('%Y%m%d%H%M%S')
    
    attrs = {
        "latitude": '45.1234567',
        "longitude": '9.1234567',
        "ops": [
            {
                "oprnCrtDate": fresh_ts,
                "oprnDoneDate": fresh_ts,
                "oprnType": 'LOCATION',
                "oprnStsCd": '2800',
                "oprnResultCode": '1200',
                "extra": {"gpsUtcDt": fresh_ts},
                "latitude": '45.1234567',
                "longitude": '9.1234567',
            }
        ],
        "gpsUtcDt": fresh_ts,
    }

    hass = FakeHass(states_map={"device_tracker.smarttagscooter": FakeState(attrs)})
    coord = VehicleCoordinator(hass, "entry1", {"device_tracker": "device_tracker.smarttagscooter", "activation_mode": "manual"})
    
    class DummyStore:
        async def async_load(self):
            return None
        async def async_save(self, data):
            return None
    coord.store = DummyStore()

    await async_register_services(hass, coord, "device_tracker.smarttagscooter", None)
    func = hass._registered_services.get(("vehicle_bt_parking_sentinel", "manual_trigger"))

    class Call:
        def __init__(self, data=None):
            self.data = data or {}

    await func(Call())
    return coord


def test_manual_save_scenario_fresh_gps():
    """Test manual_trigger with fresh GPS timestamp - should save immediately."""
    coord = asyncio.run(run_scenario_fresh_gps())
    # With fresh GPS, manual_trigger should:
    # 1. Save position immediately
    assert coord.saved_latitude is not None
    assert coord.saved_longitude is not None
    assert float(coord.saved_latitude) == 45.1234567
    assert float(coord.saved_longitude) == 9.1234567
    # 2. Enable alarm
    assert coord.alarm_active is True
    # 3. NOT set awaiting flag (GPS was fresh)
    assert getattr(coord, '_awaiting_activation_save', False) is False
