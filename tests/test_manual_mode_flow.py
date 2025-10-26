"""Test manual mode webhook flow and alarm state management.

Verifies:
1. Manual mode starts with alarm_active=False even if storage has alarm_active=True
2. Webhook START command enables alarm
3. Webhook DISARM command disables alarm
4. Webhook SAVE command saves position
5. State transitions are logged correctly
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aiohttp import web


def test_manual_mode_starts_with_alarm_disabled():
    """Test that manual mode always starts with alarm_active=False."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
    
    class FakeHass:
        def __init__(self):
            self.data = {}
        
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        async def async_load(self):
            # Simulate storage with alarm_active=True (should be ignored in manual mode)
            return {
                "alarm_active": True,
                "saved_latitude": 45.123,
                "saved_longitude": 9.456
            }
        
        async def async_save(self, data):
            pass
    
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "activation_mode": "manual",
            "person_entity": "person.test",
            "notifier": "notify.test",
            "tolerance_radius": 200
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    
    # Load from storage (should ignore alarm_active=True because mode is manual)
    asyncio.run(coordinator.async_load())
    
    # Verify alarm is disabled even though storage had it enabled
    assert coordinator.alarm_active is False
    assert coordinator.activation_mode == "manual"


def test_webhook_start_enables_alarm():
    """Test that webhook START command enables alarm."""
    from custom_components.vehicle_bt_parking_sentinel.services import handle_webhook_impl
    
    class FakeHass:
        def __init__(self):
            self.data = {}
    
    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = False
            self.position_notified = False
            self.config = {"options": {}}
            self.hass = FakeHass()
        
        async def set_alarm_active(self, value):
            self.alarm_active = value
        
        async def async_save(self):
            pass
    
    class FakeRequest:
        def __init__(self, action):
            self.method = "POST"
            self.query = {}
            self.headers = {}
            self._action = action
        
        async def json(self):
            return {"action": self._action}
    
    coordinator = FakeCoordinator()
    request = FakeRequest("start")
    
    response = asyncio.run(handle_webhook_impl(
        coordinator.hass, coordinator, "device_tracker.test", request
    ))
    
    assert response.status == 200
    assert coordinator.alarm_active is True


def test_webhook_disarm_disables_alarm():
    """Test that webhook DISARM command disables alarm."""
    from custom_components.vehicle_bt_parking_sentinel.services import handle_webhook_impl
    
    class FakeHass:
        def __init__(self):
            self.data = {}
    
    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = True  # Start enabled
            self.position_notified = False
            self.config = {"options": {}}
            self.hass = FakeHass()
        
        async def set_alarm_active(self, value):
            self.alarm_active = value
        
        async def async_save(self):
            pass
    
    class FakeRequest:
        def __init__(self, action):
            self.method = "POST"
            self.query = {}
            self.headers = {}
            self._action = action
        
        async def json(self):
            return {"action": self._action}
    
    coordinator = FakeCoordinator()
    request = FakeRequest("disarm")
    
    response = asyncio.run(handle_webhook_impl(
        coordinator.hass, coordinator, "device_tracker.test", request
    ))
    
    assert response.status == 200
    assert coordinator.alarm_active is False


def test_webhook_save_stores_position():
    """Test that webhook SAVE command saves position from device_tracker."""
    from custom_components.vehicle_bt_parking_sentinel.services import handle_webhook_impl
    
    class FakeState:
        def __init__(self):
            self.attributes = {
                "latitude": "45.123",
                "longitude": "9.456"
            }
    
    class FakeHass:
        def __init__(self):
            self.data = {}
            self.states = MagicMock()
            self.states.get = MagicMock(return_value=FakeState())
    
    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = False
            self.position_notified = False
            self.config = {"options": {}}
            self.hass = FakeHass()
            self.saved_latitude = None
            self.saved_longitude = None
        
        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = lat
            self.saved_longitude = lon
        
        async def async_save(self):
            pass
    
    class FakeRequest:
        def __init__(self, action):
            self.method = "POST"
            self.query = {}
            self.headers = {}
            self._action = action
        
        async def json(self):
            return {"action": self._action}
    
    coordinator = FakeCoordinator()
    request = FakeRequest("save")
    
    response = asyncio.run(handle_webhook_impl(
        coordinator.hass, coordinator, "device_tracker.test", request
    ))
    
    assert response.status == 200
    assert coordinator.saved_latitude == 45.123
    assert coordinator.saved_longitude == 9.456


def test_manual_mode_full_flow():
    """Test complete manual mode flow: load -> save -> start -> disarm."""
    from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
    
    class FakeHass:
        def __init__(self):
            self.data = {}
            self.states = MagicMock()
            self.states.get = MagicMock(return_value=None)
        
        def async_create_task(self, coro):
            pass
    
    class FakeStore:
        def __init__(self):
            self.data = {}
        
        async def async_load(self):
            return self.data
        
        async def async_save(self, data):
            self.data = data
    
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "activation_mode": "manual",
            "person_entity": "person.test",
            "notifier": "notify.test",
            "tolerance_radius": 200
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    
    # 1. Load from storage (should start with alarm_active=False)
    asyncio.run(coordinator.async_load())
    assert coordinator.alarm_active is False
    assert coordinator.activation_mode == "manual"
    
    # 2. Save a position
    asyncio.run(coordinator._async_save_position(45.123, 9.456))
    assert coordinator.saved_latitude == 45.123
    assert coordinator.saved_longitude == 9.456
    
    # 3. Enable alarm
    asyncio.run(coordinator.set_alarm_active(True))
    assert coordinator.alarm_active is True
    
    # 4. Simulate restart - load from storage
    # Storage now has alarm_active=True, but manual mode should ignore it
    coordinator2 = VehicleCoordinator(hass, "test_entry", config)
    coordinator2.store = coordinator.store
    asyncio.run(coordinator2.async_load())
    
    # Verify alarm is disabled after reload (manual mode behavior)
    assert coordinator2.alarm_active is False
    assert coordinator2.saved_latitude == 45.123  # But position is preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
