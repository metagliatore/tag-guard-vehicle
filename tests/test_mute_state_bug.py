"""Test that mute doesn't change state from awaiting_position to alarm_triggered."""
import pytest


@pytest.mark.asyncio
async def test_mute_from_awaiting_position_keeps_state():
    """Test that calling mute while in awaiting_position state doesn't change to alarm_triggered."""
    from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor
    
    class FakeHass:
        data = {}
    
    class FakeEntry:
        def __init__(self, entry_id):
            self.entry_id = entry_id
            self.data = {}
            self.options = {}
    
    class FakeCoordinator:
        def __init__(self):
            self.saved_latitude = None
            self.saved_longitude = None
            self.alarm_active = False
            self.position_notified = False
            self.tolerance_radius = 200
            self.stationary_minutes = 10
            self.last_tag_state = None
            self.config = {"device_tracker": "device.test"}
            self._awaiting_activation_save = False
    
    hass = FakeHass()
    entry = FakeEntry("test_entry")
    coord = FakeCoordinator()
    hass.data["vehicle_bt_parking_sentinel"] = {entry.entry_id + "_coordinator": coord}
    
    sensor = VehicleBtParkingSentinelSensor(hass, entry)
    
    # Setup: alarm active, no position, awaiting GPS (awaiting_position state)
    coord.alarm_active = True
    coord._awaiting_activation_save = True
    coord.saved_latitude = None
    coord.saved_longitude = None
    coord.position_notified = False
    
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "Initial state should be awaiting_position"
    
    # Action: mute notifications (set position_notified=True)
    coord.position_notified = True
    
    # Verify: state should STILL be awaiting_position, NOT alarm_triggered
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "State should remain awaiting_position after mute, not change to alarm_triggered"


@pytest.mark.asyncio
async def test_mute_from_awaiting_position_with_old_position():
    """Test mute doesn't trigger alarm_triggered when awaiting fresh GPS but have old position."""
    from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor
    
    class FakeHass:
        data = {}
    
    class FakeEntry:
        def __init__(self, entry_id):
            self.entry_id = entry_id
            self.data = {}
            self.options = {}
    
    class FakeCoordinator:
        def __init__(self):
            self.saved_latitude = None
            self.saved_longitude = None
            self.alarm_active = False
            self.position_notified = False
            self.tolerance_radius = 200
            self.stationary_minutes = 10
            self.last_tag_state = None
            self.config = {"device_tracker": "device.test"}
            self._awaiting_activation_save = False
    
    hass = FakeHass()
    entry = FakeEntry("test_entry")
    coord = FakeCoordinator()
    hass.data["vehicle_bt_parking_sentinel"] = {entry.entry_id + "_coordinator": coord}
    
    sensor = VehicleBtParkingSentinelSensor(hass, entry)
    
    # Setup: alarm active, HAS old position, but awaiting fresh GPS
    coord.alarm_active = True
    coord._awaiting_activation_save = True  # Waiting for fresh GPS
    coord.saved_latitude = 45.0  # Old position exists
    coord.saved_longitude = 9.0
    coord.position_notified = False
    
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "Should be awaiting_position when waiting for fresh GPS"
    
    # Action: mute notifications
    coord.position_notified = True
    
    # Verify: state should STILL be awaiting_position
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "State should remain awaiting_position after mute (not alarm_triggered)"
    
    # Now simulate GPS arrived (clear awaiting flag)
    coord._awaiting_activation_save = False
    
    # Verify: NOW it should show alarm_triggered (position exists, alarm active, position_notified=True)
    # Actually, this is a muted state, so it's more like "monitoring but silenced"
    # The logic shows alarm_triggered when movement was detected and notified
    # But in this case, position_notified=True from mute, not from actual movement
    # This is a design question: should mute show alarm_triggered or parked?
    await sensor.async_update()
    # For now, the logic will show alarm_triggered if all conditions are met
    # This might need discussion: is position_notified=True only for movement, or also for mute?
    assert sensor.state == "alarm_triggered", "After GPS arrives and mute is active, shows alarm_triggered"


@pytest.mark.asyncio
async def test_parked_then_start_again_stays_awaiting():
    """Test that calling start again while parked goes to awaiting_position and stays there."""
    from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor
    
    class FakeHass:
        data = {}
    
    class FakeEntry:
        def __init__(self, entry_id):
            self.entry_id = entry_id
            self.data = {}
            self.options = {}
    
    class FakeCoordinator:
        def __init__(self):
            self.saved_latitude = None
            self.saved_longitude = None
            self.alarm_active = False
            self.position_notified = False
            self.tolerance_radius = 200
            self.stationary_minutes = 10
            self.last_tag_state = None
            self.config = {"device_tracker": "device.test"}
            self._awaiting_activation_save = False
    
    hass = FakeHass()
    entry = FakeEntry("test_entry")
    coord = FakeCoordinator()
    hass.data["vehicle_bt_parking_sentinel"] = {entry.entry_id + "_coordinator": coord}
    
    sensor = VehicleBtParkingSentinelSensor(hass, entry)
    
    # Setup: parked state (alarm active, position saved)
    coord.alarm_active = True
    coord.saved_latitude = 45.0
    coord.saved_longitude = 9.0
    coord.position_notified = False
    coord._awaiting_activation_save = False
    
    await sensor.async_update()
    assert sensor.state == "parked", "Initial state should be parked"
    
    # Action: call start again (sets awaiting flag)
    coord._awaiting_activation_save = True
    
    # Verify: state should be awaiting_position
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "State should change to awaiting_position when waiting for fresh GPS"
    
    # Verify: even if device tracker updates with old GPS, should stay in awaiting_position
    # (not flip back to parked)
    await sensor.async_update()
    assert sensor.state == "awaiting_position", "Should remain in awaiting_position until fresh GPS arrives"
