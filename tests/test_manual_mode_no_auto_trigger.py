"""Test that manual mode does NOT auto-trigger on connection/disconnection events.

This test verifies that manual mode behaves correctly and is not affected
by the connection mode auto-trigger logic.
"""
import pytest


@pytest.mark.asyncio
async def test_manual_mode_ignores_disconnect_events():
    """Test that manual mode does NOT activate alarm on tag disconnect."""
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
        "activation_mode": "manual",  # MANUAL mode
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.last_tag_state = "connected"
    coord.alarm_active = False  # Manual mode starts disabled

    # Create disconnect event
    class FakeState:
        def __init__(self):
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
        def __init__(self):
            self.data = {
                "new_state": FakeState(),
                "old_state": None,
                "entity_id": "device.tracker_test",
            }

    event = FakeEvent()

    # Handle the disconnect event
    await coord._handle_device_event(event)

    # Verify state changed to disconnected
    assert coord.last_tag_state == "disconnected"

    # CRITICAL: Verify alarm is still DISABLED (manual mode should NOT auto-activate)
    assert coord.alarm_active is False, "Manual mode should NOT activate alarm on disconnect"

    # Verify position was NOT saved (manual mode requires explicit save command)
    assert coord.saved_latitude is None
    assert coord.saved_longitude is None


@pytest.mark.asyncio
async def test_manual_mode_ignores_connect_events():
    """Test that manual mode does NOT deactivate alarm on tag connect."""
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
        "activation_mode": "manual",  # MANUAL mode
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.last_tag_state = "disconnected"
    coord.alarm_active = True  # Manually activated
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2

    # Create connect event
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "CHECK_CONNECTION",
                        "oprnResultCode": "1200",  # Success
                        "oprnStsCd": "2800",  # Connected
                        "battery": "NORMAL",
                        "latitude": "45.6",
                        "longitude": "9.3",
                        "extra": {"gpsUtcDt": "20251102130000"},
                    },
                ],
                "latitude": 45.6,
                "longitude": 9.3,
                "gpsUtcDt": "20251102130000",
            }

    class FakeEvent:
        def __init__(self):
            self.data = {
                "new_state": FakeState(),
                "old_state": None,
                "entity_id": "device.tracker_test",
            }

    event = FakeEvent()

    # Handle the connect event
    await coord._handle_device_event(event)

    # Verify state changed to connected
    assert coord.last_tag_state == "connected"

    # CRITICAL: Verify alarm is still ENABLED (manual mode should NOT auto-deactivate)
    assert coord.alarm_active is True, "Manual mode should NOT deactivate alarm on connect"

    # Verify saved position unchanged
    assert coord.saved_latitude == 45.5
    assert coord.saved_longitude == 9.2


@pytest.mark.asyncio
async def test_manual_mode_requires_explicit_start_stop():
    """Test that manual mode only responds to explicit start/stop commands."""
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
                                "latitude": "45.7",
                                "longitude": "9.4",
                                "extra": {"gpsUtcDt": "20251102140000"},
                            }
                        ],
                        "latitude": 45.7,
                        "longitude": 9.4,
                        "gpsUtcDt": "20251102140000",
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
        "activation_mode": "manual",
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()

    # Initially alarm is disabled
    assert coord.alarm_active is False

    # Explicitly enable alarm (like webhook start command)
    # Use older activation time so GPS is considered "fresh" (newer)
    await coord.set_alarm_active(True, activation_time="20251102130000")

    # Verify alarm is now enabled
    assert coord.alarm_active is True

    # Verify position was saved (GPS timestamp is fresh: 140000 > 130000)
    assert coord.saved_latitude == 45.7
    assert coord.saved_longitude == 9.4

    # Explicitly disable alarm (like webhook stop command)
    await coord.set_alarm_active(False)

    # Verify alarm is now disabled
    assert coord.alarm_active is False

    # Verify saved position is preserved (stop doesn't clear it)
    assert coord.saved_latitude == 45.7
    assert coord.saved_longitude == 9.4
