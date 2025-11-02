"""Test connection mode with multiple instances to verify no concurrency issues.

This test verifies that connection mode works correctly with multiple instances
of the integration, each monitoring a different vehicle/device_tracker.
"""
import pytest


@pytest.mark.asyncio
async def test_connection_mode_two_instances_independent():
    """Test that two connection mode instances work independently without interference."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                return None

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    # Instance 1: Vehicle A (car)
    config1 = {
        "device_tracker": "device.tracker_car",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord1 = VehicleCoordinator(hass, "entry_car", config1)
    coord1.store = FakeStore()
    coord1.last_tag_state = "connected"
    coord1.alarm_active = False

    # Instance 2: Vehicle B (motorcycle)
    config2 = {
        "device_tracker": "device.tracker_motorcycle",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord2 = VehicleCoordinator(hass, "entry_motorcycle", config2)
    coord2.store = FakeStore()
    coord2.last_tag_state = "connected"
    coord2.alarm_active = False

    # Verify both instances are independent
    assert coord1.entry_id == "entry_car"
    assert coord2.entry_id == "entry_motorcycle"
    assert coord1.config["device_tracker"] == "device.tracker_car"
    assert coord2.config["device_tracker"] == "device.tracker_motorcycle"
    assert coord1.alarm_active is False
    assert coord2.alarm_active is False

    # Simulate disconnect event for Vehicle A only
    class FakeState:
        def __init__(self, entity_id):
            self.entity_id = entity_id
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "LOCATION",
                        "latitude": "45.5",
                        "longitude": "9.2",
                        "extra": {"gpsUtcDt": "20251102120000"},
                    },
                    {"oprnType": "CHECK_CONNECTION", "battery": "LOW"},
                ],
                "latitude": 45.5,
                "longitude": 9.2,
                "gpsUtcDt": "20251102120000",
            }

    class FakeEvent:
        def __init__(self, entity_id):
            self.data = {
                "new_state": FakeState(entity_id),
                "old_state": None,
                "entity_id": entity_id,
            }

    # Vehicle A disconnects
    event_car = FakeEvent("device.tracker_car")
    await coord1._handle_device_event(event_car)

    # Verify only coord1 (car) is affected
    assert coord1.last_tag_state == "disconnected", "Car should be disconnected"
    assert coord1.alarm_active is True, "Car alarm should be active"
    assert coord1.saved_latitude == 45.5
    assert coord1.saved_longitude == 9.2

    # Verify coord2 (motorcycle) is NOT affected
    assert coord2.last_tag_state == "connected", "Motorcycle should still be connected"
    assert coord2.alarm_active is False, "Motorcycle alarm should still be inactive"
    assert coord2.saved_latitude is None
    assert coord2.saved_longitude is None


@pytest.mark.asyncio
async def test_connection_mode_three_instances_simultaneous_events():
    """Test that three connection mode instances handle simultaneous events correctly."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                return None

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    # Create 3 instances
    coordinators = []
    vehicles = ["car", "motorcycle", "bicycle"]
    
    for vehicle in vehicles:
        config = {
            "device_tracker": f"device.tracker_{vehicle}",
            "activation_mode": "connection",
            "tag_model": "samsung_smarttag2",
            "debug_mode": True,
        }
        coord = VehicleCoordinator(hass, f"entry_{vehicle}", config)
        coord.store = FakeStore()
        coord.last_tag_state = "connected"
        coord.alarm_active = False
        coordinators.append(coord)

    # Simulate simultaneous disconnect events for all vehicles
    class FakeState:
        def __init__(self, entity_id, lat, lon):
            self.entity_id = entity_id
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "LOCATION",
                        "latitude": str(lat),
                        "longitude": str(lon),
                        "extra": {"gpsUtcDt": "20251102120000"},
                    },
                    {"oprnType": "CHECK_CONNECTION", "battery": "LOW"},
                ],
                "latitude": lat,
                "longitude": lon,
                "gpsUtcDt": "20251102120000",
            }

    class FakeEvent:
        def __init__(self, entity_id, lat, lon):
            self.data = {
                "new_state": FakeState(entity_id, lat, lon),
                "old_state": None,
                "entity_id": entity_id,
            }

    # All vehicles disconnect with different positions
    positions = [(45.5, 9.2), (45.6, 9.3), (45.7, 9.4)]
    
    for coord, (lat, lon), vehicle in zip(coordinators, positions, vehicles):
        event = FakeEvent(f"device.tracker_{vehicle}", lat, lon)
        await coord._handle_device_event(event)

    # Verify each coordinator has its own state
    for coord, (lat, lon), vehicle in zip(coordinators, positions, vehicles):
        assert coord.last_tag_state == "disconnected", f"{vehicle} should be disconnected"
        assert coord.alarm_active is True, f"{vehicle} alarm should be active"
        assert coord.saved_latitude == lat, f"{vehicle} should have lat={lat}"
        assert coord.saved_longitude == lon, f"{vehicle} should have lon={lon}"
        assert coord.entry_id == f"entry_{vehicle}"


@pytest.mark.asyncio
async def test_connection_mode_mixed_states_multiple_instances():
    """Test multiple instances with different connection states."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                return None

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    # Instance 1: disconnected (alarm ON)
    config1 = {
        "device_tracker": "device.tracker_car",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord1 = VehicleCoordinator(hass, "entry_car", config1)
    coord1.store = FakeStore()
    coord1.last_tag_state = "disconnected"
    coord1.alarm_active = True
    coord1.saved_latitude = 45.5
    coord1.saved_longitude = 9.2

    # Instance 2: connected (alarm OFF)
    config2 = {
        "device_tracker": "device.tracker_motorcycle",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord2 = VehicleCoordinator(hass, "entry_motorcycle", config2)
    coord2.store = FakeStore()
    coord2.last_tag_state = "connected"
    coord2.alarm_active = False

    # Instance 3: manual mode (for comparison)
    config3 = {
        "device_tracker": "device.tracker_bicycle",
        "activation_mode": "manual",
        "tag_model": "samsung_smarttag2",
    }
    coord3 = VehicleCoordinator(hass, "entry_bicycle", config3)
    coord3.store = FakeStore()
    coord3.last_tag_state = "connected"
    coord3.alarm_active = True  # Manually activated

    # Simulate connect event for coord1 (should deactivate)
    class FakeConnectState:
        def __init__(self, entity_id):
            self.entity_id = entity_id
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "CHECK_CONNECTION",
                        "oprnResultCode": "1200",
                        "oprnStsCd": "2800",
                        "latitude": "45.5",
                        "longitude": "9.2",
                    },
                ],
                "latitude": 45.5,
                "longitude": 9.2,
            }

    class FakeConnectEvent:
        def __init__(self, entity_id):
            self.data = {
                "new_state": FakeConnectState(entity_id),
                "old_state": None,
                "entity_id": entity_id,
            }

    # Car reconnects
    event_car_connect = FakeConnectEvent("device.tracker_car")
    await coord1._handle_device_event(event_car_connect)

    # Verify states
    assert coord1.last_tag_state == "connected", "Car should now be connected"
    assert coord1.alarm_active is False, "Car alarm should be deactivated"
    assert coord1.saved_latitude == 45.5, "Car saved position should be preserved"

    assert coord2.last_tag_state == "connected", "Motorcycle unchanged"
    assert coord2.alarm_active is False, "Motorcycle unchanged"

    assert coord3.last_tag_state == "connected", "Bicycle unchanged"
    assert coord3.alarm_active is True, "Bicycle manual alarm unchanged"


@pytest.mark.asyncio
async def test_connection_mode_manual_override_with_multiple_instances():
    """Test manual override in connection mode doesn't affect other instances."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                # Return coordinates for manual start
                class FakeState:
                    attributes = {
                        "ops": [
                            {
                                "oprnType": "LOCATION",
                                "latitude": "46.0",
                                "longitude": "9.8",
                                "extra": {"gpsUtcDt": "20251102180000"},
                            }
                        ],
                        "latitude": 46.0,
                        "longitude": 9.8,
                        "gpsUtcDt": "20251102180000",
                    }
                return FakeState()

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    # Two connection mode instances
    config1 = {
        "device_tracker": "device.tracker_car",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord1 = VehicleCoordinator(hass, "entry_car", config1)
    coord1.store = FakeStore()
    coord1.alarm_active = False

    config2 = {
        "device_tracker": "device.tracker_motorcycle",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord2 = VehicleCoordinator(hass, "entry_motorcycle", config2)
    coord2.store = FakeStore()
    coord2.alarm_active = False

    # Manually start only coord1
    await coord1.set_alarm_active(True, activation_time="20251102170000")

    # Verify only coord1 is affected
    assert coord1.alarm_active is True, "Car alarm should be manually activated"
    assert coord1.saved_latitude == 46.0

    assert coord2.alarm_active is False, "Motorcycle should be unchanged"
    assert coord2.saved_latitude is None
