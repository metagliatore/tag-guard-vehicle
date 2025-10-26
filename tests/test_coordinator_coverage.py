"""Additional coordinator tests for edge cases and better coverage."""
import pytest


@pytest.mark.asyncio
async def test_handle_device_event_with_none_new_state_returns_early():
    """Test that _handle_device_event returns early when new_state is None."""
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

    # Create event with None new_state
    class FakeEvent:
        def __init__(self):
            self.data = {"new_state": None, "old_state": None, "entity_id": "device.tracker_test"}

    event = FakeEvent()

    # Should return early without error
    await coord._handle_device_event(event)
    # No assertion needed - just verify it doesn't crash


@pytest.mark.asyncio
async def test_set_alarm_active_false_preserves_saved_position():
    """Test that disabling alarm preserves the saved position."""
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
    coord.alarm_active = True

    # Disable alarm
    await coord.set_alarm_active(False)

    # Alarm should be disabled but position preserved
    assert coord.alarm_active is False
    assert coord.saved_latitude == 45.5
    assert coord.saved_longitude == 9.2


@pytest.mark.asyncio
async def test_has_moved_returns_false_without_saved_position():
    """Test has_moved returns False when no saved position (cannot determine movement)."""
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

    # No saved position - returns False (cannot determine, avoid false alarms)
    assert coord.has_moved(45.5, 9.2, 200) is False


@pytest.mark.asyncio
async def test_has_moved_returns_false_within_tolerance():
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
async def test_has_moved_returns_true_outside_tolerance():
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
