"""Tests for state validation and auto-fixing of inconsistent states."""
import asyncio
import pytest


def test_validation_fixes_manual_mode_alarm_active_without_position():
    """Test that alarm_active is reset to False in manual mode when no saved position exists."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    class FakeHass:
        def async_create_task(self, coro):
            # no-op for this test
            pass
    
    class FakeStore:
        async def async_load(self):
            # Simulate a store with inconsistent state:
            # manual mode but alarm_active was True from a previous version
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
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    
    # Before validation, manually set alarm_active to True (simulating old state)
    coord.alarm_active = True
    
    # Call validation
    coord._validate_and_fix_state()
    
    # After validation, alarm_active should be False (no saved position in manual mode)
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
    """Test that awaiting_activation_save is enabled when alarm is active but no position saved."""
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
        "activation_mode": "connection",  # non-manual mode, so alarm starts True
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry_id", config)
    coord.store = FakeStore()
    
    # alarm_active defaults to True in connection mode
    assert coord.alarm_active is True
    
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
    
    # alarm_active defaults to True
    assert coord.alarm_active is True
    
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
