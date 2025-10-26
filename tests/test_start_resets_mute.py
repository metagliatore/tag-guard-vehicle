"""Test that start resets mute (position_notified flag)."""
import pytest


@pytest.mark.asyncio
async def test_start_resets_mute():
    """Test that calling start (set_alarm_active) resets position_notified to False."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
    
    class FakeHass:
        data = {}
        
        def async_create_task(self, coro):
            pass
        
        class States:
            def get(self, entity_id):
                return None
        
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
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    
    # Setup: alarm active, position saved, muted
    coordinator.alarm_active = True
    coordinator.saved_latitude = 45.0
    coordinator.saved_longitude = 9.0
    coordinator.position_notified = True  # Muted!
    
    # Verify initial state
    assert coordinator.position_notified is True, "Should start muted"
    
    # Action: call start again (to reset and search for new position)
    await coordinator.set_alarm_active(True)
    
    # Verify: position_notified should be reset to False (unmuted)
    assert coordinator.position_notified is False, "Start should unmute (reset position_notified to False)"
    assert coordinator.alarm_active is True, "Alarm should still be active"


@pytest.mark.asyncio
async def test_start_from_disabled_also_unmutes():
    """Test that starting from disabled state also ensures position_notified is False."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
    
    class FakeHass:
        data = {}
        
        def async_create_task(self, coro):
            pass
        
        class States:
            def get(self, entity_id):
                return None
        
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
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    
    # Setup: alarm disabled, but position_notified is True (from previous session)
    coordinator.alarm_active = False
    coordinator.saved_latitude = 45.0
    coordinator.saved_longitude = 9.0
    coordinator.position_notified = True  # Leftover from previous session
    
    # Action: start (enable alarm)
    await coordinator.set_alarm_active(True)
    
    # Verify: position_notified should be False for fresh start
    assert coordinator.position_notified is False, "Fresh start should have notifications enabled"
    assert coordinator.alarm_active is True, "Alarm should be active"


@pytest.mark.asyncio
async def test_disable_alarm_does_not_change_mute():
    """Test that disabling alarm doesn't change position_notified flag."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
    
    class FakeHass:
        data = {}
        
        def async_create_task(self, coro):
            pass
        
        class States:
            def get(self, entity_id):
                return None
        
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
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    
    # Setup: alarm active, muted
    coordinator.alarm_active = True
    coordinator.position_notified = True
    
    # Action: disable alarm
    await coordinator.set_alarm_active(False)
    
    # Verify: position_notified should remain as it was (True)
    # When user re-enables, it will be reset to False
    assert coordinator.position_notified is True, "Disabling alarm shouldn't change mute state"
    assert coordinator.alarm_active is False, "Alarm should be disabled"
