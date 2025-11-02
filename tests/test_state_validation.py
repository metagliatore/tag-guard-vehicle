"""Tests for state validation and auto-fixing of inconsistent states."""
import asyncio
import pytest


def test_validation_fixes_manual_mode_alarm_active_without_position():
    """Test that all modes now start with alarm_active=False regardless of storage.
    
    This test verifies the new behavior: all activation modes initialize with
    alarm_active=False, even if storage contains alarm_active=True from a previous session.
    """
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            # no-op for this test
            pass
    
    class FakeStore:
        async def async_load(self):
            # Storage contains alarm_active=True from previous session
            # But new behavior: all modes ignore this and start with False
            return {
                "saved_latitude": None,
                "saved_longitude": None,
                "saved_gpsUtcDt": None,
                "saved_location_type": None,
                "saved_last_seen": None,
                "position_notified": False,
                "last_tag_state": "connected",
                "alarm_active": True,  # This will be ignored
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "manual",
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    
    # New behavior: alarm_active always starts False (ignores storage)
    assert coord.alarm_active is False
    
    # Call validation (shouldn't change anything now)
    coord._validate_and_fix_state()
    
    # After validation, alarm_active should still be False
    assert coord.alarm_active is False


def test_validation_keeps_alarm_active_with_saved_position():
    """Test that alarm_active is kept True if we have a valid saved position."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        async def async_load(self):
            return {
                "saved_latitude": 45.5,
                "saved_longitude": 9.2,
                "saved_gpsUtcDt": "20251027204505",
                "saved_location_type": "basic",
                "saved_last_seen": "2025-10-27T20:45:05+00:00",
                "position_notified": False,
                "last_tag_state": "disconnected",
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "manual",
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    coord.alarm_active = True
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2
    
    # Call validation
    coord._validate_and_fix_state()
    
    # alarm_active should remain True (we have a saved position)
    assert coord.alarm_active is True


def test_validation_enables_awaiting_when_alarm_active_no_position():
    """Test that awaiting_activation_save is enabled when alarm is active but no position saved.
    
    NEW BEHAVIOR: All modes start with alarm_active=False, so we need to manually
    activate the alarm first, then validation should enable awaiting flag.
    """
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        async def async_load(self):
            return {
                "saved_latitude": None,
                "saved_longitude": None,
                "saved_gpsUtcDt": None,
                "saved_location_type": None,
                "saved_last_seen": None,
                "position_notified": False,
                "last_tag_state": "connected",
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "position",
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    
    # New behavior: all modes start with alarm_active=False
    assert coord.alarm_active is False
    
    # Manually activate alarm (simulating user/automatic activation)
    coord.alarm_active = True
    
    # awaiting flag is False by default
    coord._awaiting_activation_save = False
    
    # Call validation
    coord._validate_and_fix_state()
    
    # awaiting_activation_save should now be True (alarm active, no saved position)
    assert coord._awaiting_activation_save is True
    assert coord._activation_time_str is not None


def test_validation_does_not_enable_awaiting_when_position_exists():
    """Test that awaiting flag is NOT enabled if we already have a saved position."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        async def async_load(self):
            return {
                "saved_latitude": 45.5,
                "saved_longitude": 9.2,
                "saved_gpsUtcDt": "20251027204505",
                "saved_location_type": "basic",
                "saved_last_seen": "2025-10-27T20:45:05+00:00",
                "position_notified": False,
                "last_tag_state": "disconnected",
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "connection",
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    coord.saved_latitude = 45.5
    coord.saved_longitude = 9.2
    
    # Connection mode starts with alarm_active False (like manual mode)
    assert coord.alarm_active is False
    
    # awaiting flag starts False
    coord._awaiting_activation_save = False
    
    # Call validation
    coord._validate_and_fix_state()
    
    # awaiting_activation_save should remain False (we have a position)
    assert coord._awaiting_activation_save is False


@pytest.mark.asyncio
async def test_validation_runs_after_async_load():
    """Test that _validate_and_fix_state is called automatically after async_load."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        async def async_load(self):
            return {
                "saved_latitude": None,
                "saved_longitude": None,
                "saved_gpsUtcDt": None,
                "saved_location_type": None,
                "saved_last_seen": None,
                "position_notified": False,
                "last_tag_state": "connected",
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device.tracker_test",
        "activation_mode": "manual",
        "debug_mode": False,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    
    # Manually set alarm to True before load
    coord.alarm_active = True
    
    # Call async_load
    await coord.async_load()
    
    # Validation should have run and reset alarm_active to False
    assert coord.alarm_active is False
