"""Tests for edge cases and uncovered branches in coordinator."""
import asyncio
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_handle_device_event_with_none_new_state():
    """Test that _handle_device_event returns early when new_state is None."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "manual",
        "debug_mode": False,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()

    # Create event with None new_state
    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": None, "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Should return early without error
    await coord._handle_device_event(event)
    # No assertion needed - just verify it doesn't crash


@pytest.mark.asyncio
async def test_handle_device_event_connection_state_change():
    """Test tag state change from connected to disconnected."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

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

        services = Services()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.last_tag_state = "connected"
    coord.alarm_active = True

    # Create event with disconnected state
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "LOCATION",
                        "latitude": "45.5",
                        "longitude": "9.2",
                        "extra": {"gpsUtcDt": "20251028120000"},
                    },
                    {"oprnType": "CHECK_CONNECTION", "battery": "LOW"},
                ],
                "latitude": 45.5,
                "longitude": 9.2,
                "gpsUtcDt": "20251028120000",
            }

    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": FakeState(), "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Handle the event
    await coord._handle_device_event(event)

    # Verify state changed
    assert coord.last_tag_state == "disconnected"
    # Position should be saved
    assert coord.saved_latitude == 45.5
    assert coord.saved_longitude == 9.2


@pytest.mark.asyncio
async def test_handle_device_event_movement_detection():
    """Test movement detection when alarm is active."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

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

        services = Services()

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
        "notifier": "notify.test",
        "tolerance_radius": 200,
        "debug_mode": False,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.alarm_active = True
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2
    coord.position_notified = False

    # Create event with moved coordinates (far away)
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [{"oprnType": "LOCATION", "latitude": "45.6", "longitude": "9.3"}],
                "latitude": 45.6,
                "longitude": 9.3,
            }

    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": FakeState(), "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Handle the event
    await coord._handle_device_event(event)

    # Verify notification was called
    assert coord.position_notified is True
    assert len(hass.services.calls) > 0
    assert hass.services.calls[0][0] == "notify"
    # Service name without the notify prefix (it gets stripped by _notify_movement)
    assert hass.services.calls[0][1] == "test"


@pytest.mark.asyncio
async def test_stationary_counter_reset_when_moved():
    """Test that stationary counter resets when vehicle moves."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def __init__(self):
            # Add event loop for async_call_later
            import asyncio

            self.loop = asyncio.get_event_loop()

        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        def async_run_hass_job(self, job, *args):
            # Mock for async_run_hass_job
            pass

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "position",
        "tag_model": "samsung_smarttag2",
        "tolerance_radius": 50,
        "debug_mode": False,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord._stationary_counter = 5
    coord._stationary_candidate = (45.5, 9.2)

    # Create event with different coordinates (outside tolerance)
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [{"latitude": "45.7", "longitude": "9.4"}],
                "latitude": 45.7,
                "longitude": 9.4,
            }

    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": FakeState(), "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Handle the event
    await coord._handle_device_event(event)

    # Counter should reset to 1 with new candidate
    assert coord._stationary_counter == 1
    assert coord._stationary_candidate is not None
    assert coord._stationary_candidate[0] == 45.7
    assert coord._stationary_candidate[1] == 9.4
    
    # Cleanup: cancel the stationary timer if it was created
    if coord._stationary_handle:
        coord._stationary_handle()
        coord._stationary_handle = None


@pytest.mark.asyncio
async def test_awaiting_activation_save_with_fresh_gps():
    """Test that awaiting_activation_save completes when fresh GPS arrives."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

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
    coord._awaiting_activation_save = True
    coord._activation_time_str = "20251028100000"

    # Create event with fresh GPS (after activation time)
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [
                    {
                        "extra": {"gpsUtcDt": "20251028120000"},
                        "latitude": "45.5",
                        "longitude": "9.2",
                        "gpsUtcDt": "20251028120000",
                    }
                ],
                "latitude": 45.5,
                "longitude": 9.2,
                "gpsUtcDt": "20251028120000",
                "last_seen": "2025-10-28T12:00:00+00:00",
            }

    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": FakeState(), "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Handle the event
    await coord._handle_device_event(event)

    # Awaiting flag should be cleared
    assert coord._awaiting_activation_save is False
    # Position should be saved
    assert coord.saved_latitude == 45.5
    assert coord.saved_longitude == 9.2
    assert coord.saved_gpsUtcDt == "20251028120000"


@pytest.mark.asyncio
async def test_awaiting_activation_save_with_stale_gps():
    """Test that awaiting_activation_save stays active when GPS is stale."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

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
    coord._awaiting_activation_save = True
    coord._activation_time_str = "20251028120000"

    # Create event with stale GPS (before activation time)
    class FakeState:
        def __init__(self):
            self.attributes = {
                "ops": [
                    {
                        "extra": {"gpsUtcDt": "20251028100000"},  # Old timestamp
                        "latitude": "45.5",
                        "longitude": "9.2",
                    }
                ],
                "latitude": 45.5,
                "longitude": 9.2,
                "gpsUtcDt": "20251028100000",
            }

    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": FakeState(), "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Handle the event
    await coord._handle_device_event(event)

    # Awaiting flag should remain active
    assert coord._awaiting_activation_save is True
    # Position should NOT be saved
    assert coord.saved_latitude is None
    assert coord.saved_longitude is None


@pytest.mark.asyncio
async def test_set_alarm_active_enables_and_disables():
    """Test set_alarm_active with enable and disable."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                class FakeState:
                    attributes = {"latitude": 45.5, "longitude": 9.2, "ops": []}

                return FakeState()

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
        "debug_mode": False,
    }

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()

    # Enable alarm
    await coord.set_alarm_active(True)
    assert coord.alarm_active is True

    # Disable alarm
    await coord.set_alarm_active(False)
    assert coord.alarm_active is False
    # Position should be cleared
    assert coord.saved_latitude is None
    assert coord.saved_longitude is None


@pytest.mark.asyncio
async def test_has_moved_without_saved_position():
    """Test has_moved returns False when no saved position."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {"device_tracker": "device.tracker_test", "activation_mode": "manual"}

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()

    # No saved position
    assert coord.has_moved(45.5, 9.2, 200) is False


@pytest.mark.asyncio
async def test_has_moved_with_saved_position_within_tolerance():
    """Test has_moved returns False when within tolerance."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {"device_tracker": "device.tracker_test", "activation_mode": "manual"}

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2

    # Same position (0m away)
    assert coord.has_moved(45.5, 9.2, 200) is False


@pytest.mark.asyncio
async def test_has_moved_with_saved_position_outside_tolerance():
    """Test has_moved returns True when outside tolerance."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator

    class FakeHass:
        def async_create_task(self, coro):
            pass

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    config = {"device_tracker": "device.tracker_test", "activation_mode": "manual"}

    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2

    # Far position (~11km away)
    assert coord.has_moved(45.6, 9.3, 200) is True
