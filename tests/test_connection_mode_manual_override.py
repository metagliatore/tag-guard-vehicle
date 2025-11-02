"""Test that connection mode allows manual commands (webhook/service) to override automatic behavior.

This test verifies that even when using connection mode (automatic on disconnect/connect),
the user can still manually control the alarm using webhook commands or service calls.
"""
import pytest


@pytest.mark.asyncio
async def test_connection_mode_manual_start_override():
    """Test that manual START command works in connection mode even when tag is connected."""
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
                # Return a fake state with coordinates
                class FakeDeviceState:
                    attributes = {
                        "ops": [
                            {
                                "oprnType": "LOCATION",
                                "latitude": "45.8",
                                "longitude": "9.5",
                                "extra": {"gpsUtcDt": "20251102150000"},
                            }
                        ],
                        "latitude": 45.8,
                        "longitude": 9.5,
                        "gpsUtcDt": "20251102150000",
                    }

                return FakeDeviceState()

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",  # CONNECTION mode
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.last_tag_state = "connected"  # Tag is CONNECTED
    coord.alarm_active = False  # Alarm is OFF

    # MANUALLY start alarm (like webhook command) even though tag is connected
    await coord.set_alarm_active(True, activation_time="20251102140000")

    # Verify alarm is now enabled
    assert coord.alarm_active is True, "Manual start should work in connection mode"

    # Verify position was saved (GPS is fresh)
    assert coord.saved_latitude == 45.8
    assert coord.saved_longitude == 9.5


@pytest.mark.asyncio
async def test_connection_mode_manual_stop_override():
    """Test that manual STOP command works in connection mode even when tag is disconnected."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []

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
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",  # CONNECTION mode
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.last_tag_state = "disconnected"  # Tag is DISCONNECTED
    coord.alarm_active = True  # Alarm is ON (auto-activated on disconnect)
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2

    # MANUALLY stop alarm (like webhook command) even though tag is disconnected
    await coord.set_alarm_active(False)

    # Verify alarm is now disabled
    assert coord.alarm_active is False, "Manual stop should work in connection mode"

    # Verify saved position is preserved
    assert coord.saved_latitude == 45.5
    assert coord.saved_longitude == 9.2


@pytest.mark.asyncio
async def test_connection_mode_manual_save_override():
    """Test that manual SAVE command works in connection mode."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            self._tasks = []

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
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",  # CONNECTION mode
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.alarm_active = True

    # MANUALLY save position (like webhook save command)
    await coord._async_save_position(45.9, 9.6, gpsUtcDt="20251102160000", reason="manual_save")

    # Verify position was saved
    assert coord.saved_latitude == 45.9
    assert coord.saved_longitude == 9.6
    assert coord.saved_gpsUtcDt == "20251102160000"


@pytest.mark.asyncio
async def test_connection_mode_webhook_start_action():
    """Test webhook START action in connection mode using services module."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl
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
                # Return coordinates
                class FakeState:
                    attributes = {
                        "ops": [
                            {
                                "oprnType": "LOCATION",
                                "latitude": "46.0",
                                "longitude": "9.7",
                                "extra": {"gpsUtcDt": "20251102170000"},
                            }
                        ],
                        "latitude": 46.0,
                        "longitude": 9.7,
                        "gpsUtcDt": "20251102170000",
                    }

                return FakeState()

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    class FakeRequest:
        def __init__(self):
            self.method = "POST"
            self.query = {}
            self.headers = {}

        async def json(self):
            return {"action": "start"}

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",  # CONNECTION mode
        "tag_model": "samsung_smarttag2",
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.alarm_active = False

    request = FakeRequest()

    # Call webhook START action
    response = await handle_webhook_impl(hass, coord, "device.tracker_test", request)

    # Verify response is successful
    assert response.status == 200

    # Verify alarm is now enabled
    assert coord.alarm_active is True


@pytest.mark.asyncio
async def test_connection_mode_webhook_stop_action():
    """Test webhook STOP action in connection mode using services module."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl
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

    class FakeRequest:
        def __init__(self):
            self.method = "POST"
            self.query = {}
            self.headers = {}

        async def json(self):
            return {"action": "stop"}

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",  # CONNECTION mode
        "tag_model": "samsung_smarttag2",
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.alarm_active = True  # Currently active
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2

    request = FakeRequest()

    # Call webhook STOP action
    response = await handle_webhook_impl(hass, coord, "device.tracker_test", request)

    # Verify response is successful
    assert response.status == 200

    # Verify alarm is now disabled
    assert coord.alarm_active is False
