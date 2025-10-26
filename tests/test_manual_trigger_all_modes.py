"""Test that manual_trigger works in all activation modes, not just 'manual'."""
import asyncio
from datetime import datetime, timedelta

from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
from custom_components.vehicle_bt_parking_sentinel.services import async_register_services


class FakeHass:
    def __init__(self, states_map=None):
        self.services = self
        self._states = states_map or {}
        self._registered_services = {}

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

    async def async_call(self, domain, service, data):
        self._last_call = (domain, service, data)
        return None


class FakeState:
    def __init__(self, attrs: dict):
        self.attributes = attrs


class DummyStore:
    async def async_load(self):
        return None

    async def async_save(self, data):
        return None


async def run_manual_trigger_in_mode(activation_mode: str):
    """Test manual_trigger in a specific activation mode."""
    # Create fresh GPS timestamp (future time to ensure it's considered fresh)
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

    hass = FakeHass(states_map={"device_tracker.test": FakeState(attrs)})
    coord = VehicleCoordinator(
        hass, 
        "entry1", 
        {
            "device_tracker": "device_tracker.test", 
            "activation_mode": activation_mode
        }
    )
    coord.store = DummyStore()

    await async_register_services(hass, coord, "device_tracker.test", None)
    
    # Get manual_trigger function
    func = hass._registered_services.get(("vehicle_bt_parking_sentinel", "manual_trigger"))
    assert func is not None, f"manual_trigger should be registered in {activation_mode} mode"

    class Call:
        def __init__(self, data=None):
            self.data = data or {}

    # Call manual_trigger
    await func(Call())
    
    return coord


def test_manual_trigger_in_connection_mode():
    """Verify manual_trigger works in 'connection' mode."""
    coord = asyncio.run(run_manual_trigger_in_mode("connection"))
    
    # Should save position and enable alarm
    assert coord.saved_latitude is not None
    assert coord.saved_longitude is not None
    assert coord.alarm_active is True


def test_manual_trigger_in_position_mode():
    """Verify manual_trigger works in 'position' mode."""
    coord = asyncio.run(run_manual_trigger_in_mode("position"))
    
    # Should save position and enable alarm
    assert coord.saved_latitude is not None
    assert coord.saved_longitude is not None
    assert coord.alarm_active is True


def test_manual_trigger_in_combined_mode():
    """Verify manual_trigger works in 'combined' mode."""
    coord = asyncio.run(run_manual_trigger_in_mode("combined"))
    
    # Should save position and enable alarm
    assert coord.saved_latitude is not None
    assert coord.saved_longitude is not None
    assert coord.alarm_active is True


def test_manual_trigger_in_manual_mode():
    """Verify manual_trigger works in 'manual' mode (obviously)."""
    coord = asyncio.run(run_manual_trigger_in_mode("manual"))
    
    # Should save position and enable alarm
    assert coord.saved_latitude is not None
    assert coord.saved_longitude is not None
    assert coord.alarm_active is True
