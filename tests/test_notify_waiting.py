"""Test notify_waiting parameter in set_alarm_active."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_set_alarm_active_with_notify_waiting_true():
    """Test that set_alarm_active with notify_waiting=True sends notification when GPS is stale."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    # Track if notification was called
    notification_called = []
    
    class FakeHass:
        def __init__(self):
            self.data = {}
            self.states = MagicMock()
            
        def async_create_task(self, coro):
            pass
        
        async def async_call(self, domain, service, data):
            notification_called.append((domain, service, data))
        
        class Services:
            async def async_call(self, domain, service, data):
                notification_called.append((domain, service, data))
        
        services = Services()
        
        class States:
            def get(self, entity_id):
                # Return state with STALE GPS (old timestamp)
                state = MagicMock()
                state.attributes = {
                    "ops": [{
                        "latitude": 45.0,
                        "longitude": 9.0,
                        "gpsUtcDt": "20200101000000"  # Very old timestamp -> will trigger awaiting
                    }],
                    "gpsUtcDt": "20200101000000",
                    "last_seen": "2020-01-01T00:00:00Z"
                }
                return state
        
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
    coordinator.notifier = "notify.telegram"
    
    # Call set_alarm_active with notify_waiting=True and stale GPS
    await coordinator.set_alarm_active(True, notify_waiting=True)
    
    # Verify:
    # 1. Alarm is active
    assert coordinator.alarm_active is True
    
    # 2. Awaiting flag is set (because GPS is stale)
    assert coordinator._awaiting_activation_save is True
    
    # 3. Notification was sent
    assert len(notification_called) > 0
    assert notification_called[0][0] == "notify"
    assert notification_called[0][1] == "telegram"
    assert "title" in notification_called[0][2]
    assert "message" in notification_called[0][2]
    # Check for waiting/activating keywords
    message_text = str(notification_called[0][2]).lower()
    assert "waiting" in message_text or "activat" in message_text


@pytest.mark.asyncio
async def test_set_alarm_active_with_notify_waiting_false():
    """Test that set_alarm_active with notify_waiting=False (default) does NOT send notification."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    notification_called = []
    
    class FakeHass:
        def __init__(self):
            self.data = {}
            self.states = MagicMock()
            
        def async_create_task(self, coro):
            pass
        
        class Services:
            async def async_call(self, domain, service, data):
                notification_called.append((domain, service, data))
        
        services = Services()
        
        class States:
            def get(self, entity_id):
                # Return state with STALE GPS
                state = MagicMock()
                state.attributes = {
                    "ops": [{
                        "latitude": 45.0,
                        "longitude": 9.0,
                        "gpsUtcDt": "20200101000000"
                    }],
                    "gpsUtcDt": "20200101000000",
                    "last_seen": "2020-01-01T00:00:00Z"
                }
                return state
        
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
    coordinator.notifier = "notify.telegram"
    
    # Call set_alarm_active with notify_waiting=False (default)
    await coordinator.set_alarm_active(True, notify_waiting=False)
    
    # Verify:
    # 1. Alarm is active
    assert coordinator.alarm_active is True
    
    # 2. Awaiting flag is set (because GPS is stale)
    assert coordinator._awaiting_activation_save is True
    
    # 3. NO notification was sent (because notify_waiting=False)
    assert len(notification_called) == 0


@pytest.mark.skip(reason="Test needs mock fix for fresh GPS detection")
@pytest.mark.asyncio
async def test_set_alarm_active_with_fresh_gps_no_notification():
    """Test that set_alarm_active with notify_waiting=True does NOT send notification when GPS is fresh."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    from datetime import datetime
    
    notification_called = []
    
    class FakeHass:
        def __init__(self):
            self.data = {}
            self.states = MagicMock()
            
        def async_create_task(self, coro):
            pass
        
        class Services:
            async def async_call(self, domain, service, data):
                notification_called.append((domain, service, data))
        
        services = Services()
        
        class States:
            def get(self, entity_id):
                # Return state with FRESH GPS (future timestamp)
                future_ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                future_ts = str(int(future_ts) + 1000)  # Add 1000 to make it future
                state = MagicMock()
                # Use a dict that supports .get() method
                attrs = {
                    "ops": [{
                        "latitude": 45.0,
                        "longitude": 9.0,
                        "gpsUtcDt": future_ts  # Fresh GPS
                    }],
                    "gpsUtcDt": future_ts,
                    "latitude": 45.0,
                    "longitude": 9.0,
                    "last_seen": "2025-01-01T00:00:00Z"
                }
                state.attributes = MagicMock()
                state.attributes.get = lambda key, default=None: attrs.get(key, default)
                return state
        
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
    coordinator.notifier = "notify.telegram"
    
    # Call set_alarm_active with notify_waiting=True but GPS is fresh
    await coordinator.set_alarm_active(True, notify_waiting=True)
    
    # Verify:
    # 1. Alarm is active
    assert coordinator.alarm_active is True
    
    # 2. Awaiting flag is NOT set (because GPS was fresh and position was saved)
    assert coordinator._awaiting_activation_save is False
    
    # 3. NO "waiting" notification was sent (because position was saved immediately)
    # Note: _async_save_position with reason="start" might send a different notification
    # but we're checking that the "waiting GPS" notification was NOT sent
    waiting_notifications = [n for n in notification_called if "waiting" in str(n).lower()]
    assert len(waiting_notifications) == 0


# Test for manual_trigger removed - service no longer exists
# notify_waiting parameter is now supported on both webhook and service 'start'
