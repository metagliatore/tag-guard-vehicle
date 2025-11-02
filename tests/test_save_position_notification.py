"""Test that save position sends correct notification aligned with old logic."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_save_with_fresh_gps_sends_position_saved_notification():
    """Test that save with fresh GPS sends 'Position saved' notification."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    notifications_sent = []
    
    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass
    
    class FakeHass:
        def __init__(self):
            self.services = self
            self.states_map = {}
        
        class States:
            def __init__(self, parent):
                self.parent = parent
            def get(self, entity_id):
                return self.parent.states_map.get(entity_id)
        
        @property
        def states(self):
            return self.States(self)
        
        async def async_call(self, domain, service, data):
            if domain == "notify":
                notifications_sent.append({
                    'domain': domain,
                    'service': service,
                    'title': data.get('title'),
                    'message': data.get('message')
                })
    
    class FakeState:
        def __init__(self):
            # Fresh GPS timestamp (future)
            future_time = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            future_timestamp = int(future_time) + 100
            
            self.attributes = {
                "latitude": 45.123,
                "longitude": 9.456,
                "ops": [{"extra": {"gpsUtcDt": str(future_timestamp), "locationType": "gps"}}],
                "last_seen": "2024-01-01T12:00:00"
            }
    
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "notifier": "notify.telegram",
        "options": {}
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    coordinator.notifier = "notify.telegram"
    hass.states_map["device_tracker.test"] = FakeState()
    
    # Call save with fresh GPS
    await coordinator._async_save_position_with_freshness_check(
        45.123, 9.456, require_fresh_position=True, reason="save"
    )
    
    # Verify: should have saved immediately
    assert coordinator.saved_latitude == 45.123
    assert coordinator.saved_longitude == 9.456
    
    # Verify: should send "Position saved" notification
    assert len(notifications_sent) == 1
    notification = notifications_sent[0]
    assert "Position saved" in notification['title'] or "📍" in notification['title']
    assert "https://maps.google.com" in notification['message']
    print(f"✅ Notification sent: {notification['title']}")


@pytest.mark.asyncio
async def test_save_waiting_then_fresh_gps_arrives_sends_position_saved():
    """Test that when save is waiting and fresh GPS arrives, it sends 'Position saved' notification (not 'Monitoring activated')."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    notifications_sent = []
    
    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass
    
    class FakeHass:
        def __init__(self):
            self.services = self
            self.states_map = {}
            self.data = {}
        
        def async_create_task(self, coro):
            import asyncio
            return asyncio.create_task(coro)
        
        class States:
            def __init__(self, parent):
                self.parent = parent
            def get(self, entity_id):
                return self.parent.states_map.get(entity_id)
        
        @property
        def states(self):
            return self.States(self)
        
        async def async_call(self, domain, service, data):
            if domain == "notify":
                notifications_sent.append({
                    'domain': domain,
                    'service': service,
                    'title': data.get('title'),
                    'message': data.get('message')
                })
    
    class FakeStateStale:
        """State with STALE GPS."""
        def __init__(self):
            self.attributes = {
                "latitude": 45.123,
                "longitude": 9.456,
                "ops": [{"extra": {"gpsUtcDt": "20200101120000", "locationType": "gps"}}],
                "last_seen": "2024-01-01T12:00:00"
            }
    
    class FakeStateFresh:
        """State with FRESH GPS."""
        def __init__(self, lat, lon):
            future_time = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            future_timestamp = int(future_time) + 100
            
            self.attributes = {
                "latitude": lat,
                "longitude": lon,
                "ops": [{"extra": {"gpsUtcDt": str(future_timestamp), "locationType": "gps"}}],
                "gpsUtcDt": str(future_timestamp),
                "last_seen": "2024-01-01T12:05:00"
            }
    
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "activation_mode": "manual",
        "options": {}
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    coordinator.notifier = "notify.telegram"
    coordinator.alarm_active = False  # Save without alarm active
    
    # Step 1: Call save with STALE GPS and notify_waiting=True
    hass.states_map["device_tracker.test"] = FakeStateStale()
    await coordinator._async_save_position_with_freshness_check(
        45.123, 9.456, require_fresh_position=True, notify_waiting=True, reason="save"
    )
    
    # Verify: should be waiting
    assert coordinator._awaiting_activation_save == True
    assert coordinator.saved_latitude is None  # Not saved yet
    
    # Verify: should have sent "Waiting" notification
    assert len(notifications_sent) == 1
    wait_notification = notifications_sent[0]
    assert "Waiting" in wait_notification['title'] or "⏳" in wait_notification['title']
    print(f"✅ Waiting notification sent: {wait_notification['title']}")
    
    notifications_sent.clear()
    
    # Step 2: Simulate fresh GPS arrival via device tracker event
    hass.states_map["device_tracker.test"] = FakeStateFresh(45.124, 9.457)
    
    # Create a fake event
    from homeassistant.core import Event
    event_data = {
        "entity_id": "device_tracker.test",
        "old_state": None,
        "new_state": hass.states_map["device_tracker.test"]
    }
    
    # Manually trigger the device event handler
    from unittest.mock import MagicMock
    event = MagicMock()
    event.data = event_data
    
    await coordinator._handle_device_event(event)
    
    # Verify: should have saved now
    assert coordinator.saved_latitude == 45.124
    assert coordinator.saved_longitude == 9.457
    assert coordinator._awaiting_activation_save == False
    
    # Verify: should send "Position saved" notification (NOT "Monitoring activated")
    # Because alarm_active=False, so reason should be "save"
    assert len(notifications_sent) == 1
    save_notification = notifications_sent[0]
    assert "Position saved" in save_notification['title'] or "📍" in save_notification['title']
    assert "Monitoring activated" not in save_notification['title']  # Should NOT be this
    assert "https://maps.google.com" in save_notification['message']
    print(f"✅ Position saved notification sent: {save_notification['title']}")
    print(f"✅ Message: {save_notification['message']}")


@pytest.mark.asyncio
async def test_start_waiting_then_fresh_gps_sends_monitoring_activated():
    """Test that when START is waiting and fresh GPS arrives, it sends 'Monitoring activated' notification."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    notifications_sent = []
    
    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass
    
    class FakeHass:
        def __init__(self):
            self.services = self
            self.states_map = {}
            self.data = {}
        
        def async_create_task(self, coro):
            import asyncio
            return asyncio.create_task(coro)
        
        class States:
            def __init__(self, parent):
                self.parent = parent
            def get(self, entity_id):
                return self.parent.states_map.get(entity_id)
        
        @property
        def states(self):
            return self.States(self)
        
        async def async_call(self, domain, service, data):
            if domain == "notify":
                notifications_sent.append({
                    'domain': domain,
                    'service': service,
                    'title': data.get('title'),
                    'message': data.get('message')
                })
    
    class FakeStateStale:
        """State with STALE GPS."""
        def __init__(self):
            self.attributes = {
                "latitude": 45.123,
                "longitude": 9.456,
                "ops": [{"extra": {"gpsUtcDt": "20200101120000", "locationType": "gps"}}],
                "last_seen": "2024-01-01T12:00:00"
            }
    
    class FakeStateFresh:
        """State with FRESH GPS."""
        def __init__(self, lat, lon):
            future_time = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            future_timestamp = int(future_time) + 100
            
            self.attributes = {
                "latitude": lat,
                "longitude": lon,
                "ops": [{"extra": {"gpsUtcDt": str(future_timestamp), "locationType": "gps"}}],
                "gpsUtcDt": str(future_timestamp),
                "last_seen": "2024-01-01T12:05:00"
            }
    
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "activation_mode": "manual",
        "options": {}
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    coordinator.notifier = "notify.telegram"
    
    # Step 1: Call set_alarm_active with STALE GPS and notify_waiting=True
    hass.states_map["device_tracker.test"] = FakeStateStale()
    await coordinator.set_alarm_active(True, notify_waiting=True)
    
    # Verify: should be waiting and alarm should be active
    assert coordinator._awaiting_activation_save == True
    assert coordinator.alarm_active == True
    assert coordinator.saved_latitude is None  # Not saved yet
    
    # Verify: should have sent "Waiting" notification
    assert len(notifications_sent) == 1
    wait_notification = notifications_sent[0]
    assert "Waiting" in wait_notification['title'] or "⏳" in wait_notification['title']
    print(f"✅ Waiting notification sent: {wait_notification['title']}")
    
    notifications_sent.clear()
    
    # Step 2: Simulate fresh GPS arrival
    hass.states_map["device_tracker.test"] = FakeStateFresh(45.124, 9.457)
    
    from unittest.mock import MagicMock
    event = MagicMock()
    event.data = {
        "entity_id": "device_tracker.test",
        "old_state": None,
        "new_state": hass.states_map["device_tracker.test"]
    }
    
    await coordinator._handle_device_event(event)
    
    # Verify: should have saved now
    assert coordinator.saved_latitude == 45.124
    assert coordinator.saved_longitude == 9.457
    assert coordinator._awaiting_activation_save == False
    
    # Verify: should send "Monitoring activated" notification (because alarm_active=True)
    assert len(notifications_sent) == 1
    start_notification = notifications_sent[0]
    assert "Monitoring activated" in start_notification['title'] or "🟢" in start_notification['title']
    assert "Position saved" not in start_notification['title']  # Should NOT be this
    assert "https://maps.google.com" in start_notification['message']
    print(f"✅ Monitoring activated notification sent: {start_notification['title']}")
    print(f"✅ Message: {start_notification['message']}")
