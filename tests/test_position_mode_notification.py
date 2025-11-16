"""Test notification in position mode when stationary check passes."""
import pytest
from datetime import datetime, timedelta


class FakeHass:
    def __init__(self):
        self._tasks = []
        self.data = {}
        self.notification_calls = []
        self.states = self.States()
        self.services = self.Services(self)

    def async_create_task(self, coro):
        self._tasks.append(coro)

    class Services:
        def __init__(self, parent):
            self.parent = parent

        async def async_call(self, domain, service, data):
            self.parent.notification_calls.append({
                "domain": domain,
                "service": service,
                "data": data
            })

    class States:
        def __init__(self):
            self._states = {}
            
        def async_set(self, entity_id, state, attributes=None):
            """Set state for an entity."""
            class FakeState:
                def __init__(self, state_val, attrs):
                    self.state = state_val
                    self.attributes = attrs or {}
            
            self._states[entity_id] = FakeState(state, attributes)
            
        def get(self, entity_id):
            # Return saved state if exists
            if entity_id in self._states:
                return self._states[entity_id]
            return None


class FakeStore:
    def __init__(self):
        self.data = {}
        
    async def async_load(self):
        return self.data.copy() if self.data else None

    async def async_save(self, data):
        self.data = data.copy()


@pytest.mark.asyncio
async def test_position_mode_sends_notification_on_stationary():
    """Verify that a notification is sent when position becomes stationary in position mode."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    hass = FakeHass()
    
    # Add device tracker to hass with fresh GPS timestamp
    future_time = datetime.now() + timedelta(hours=1)
    gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
    
    hass.states.async_set("device_tracker.smarttag", "home", {
        "latitude": 45.5,
        "longitude": 9.2,
        "gps_accuracy": 10,
        "gpsUtcDt": gps_timestamp,
        "friendly_name": "SmartTag Scooter",
    })
    
    config = {
        "device_tracker": "device_tracker.smarttag",
        "activation_mode": "position",
        "notifier": "notify.mobile_app",
        "webhook_token": "test_token_position",
        "person": "person.test",
        "stationary_minutes": 10,
        "stationary_count": 3,
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Set stationary counter to meet threshold (stationary_count = 3)
    coord._stationary_counter = 3
    
    # Simulate stationary check being called (this is what happens after timer expires)
    # The stationary check will save position with reason="stationary"
    await coord._stationary_check(45.5, 9.2)
    
    # Verify notification was sent
    assert len(hass.notification_calls) == 1, f"One notification should be sent, got {len(hass.notification_calls)}"
    
    notif = hass.notification_calls[0]
    assert notif["domain"] == "notify", "Notification domain should be 'notify'"
    assert notif["service"] == "mobile_app", "Service should match configured notifier"
    assert "title" in notif["data"], "Notification should have a title"
    assert "message" in notif["data"], "Notification should have a message"
    
    # Check content
    title = notif["data"]["title"]
    message = notif["data"]["message"]
    
    assert "Monitoring activated" in title or "Monitoraggio attivato" in title, f"Title should mention activation: {title}"
    assert "[" in title and "]" in title, "Title should include vehicle name in brackets"
    assert "stable" in message.lower() or "stabile" in message.lower() or "alarm" in message.lower(), f"Message should mention stable/alarm: {message}"
    assert "Mode:" in message or "Modalità:" in message or "Режим:" in message, "Message should mention mode"
    assert "https://maps.google.com" in message, "Message should include map URL"
    
    print(f"\n✓ Position mode notification sent successfully!")
    print(f"  Title: {title}")
    print(f"  Message: {message}")


@pytest.mark.asyncio
async def test_position_mode_no_notification_without_notifier():
    """Verify that no notification is sent if notifier is not configured."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    hass = FakeHass()
    
    # Add device tracker with fresh GPS
    future_time = datetime.now() + timedelta(hours=1)
    gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
    
    hass.states.async_set("device_tracker.smarttag", "home", {
        "latitude": 45.5,
        "longitude": 9.2,
        "gpsUtcDt": gps_timestamp,
        "friendly_name": "SmartTag Scooter",
    })
    
    config = {
        "device_tracker": "device_tracker.smarttag",
        "activation_mode": "position",
        "notifier": None,  # No notifier configured
        "webhook_token": "test_token_position_no_notif",
        "person": "person.test",
        "stationary_minutes": 10,
        "stationary_count": 3,
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Set stationary counter to meet threshold
    coord._stationary_counter = 3
    
    # Simulate stationary check
    await coord._stationary_check(45.5, 9.2)
    
    # Position should be saved but NO notification sent
    assert coord.saved_latitude == 45.5, "Position should be saved"
    assert len(hass.notification_calls) == 0, "No notification should be sent without notifier"
    
    print("✓ No notification sent when notifier is not configured (correct behavior)")


@pytest.mark.asyncio
async def test_position_mode_respects_stationary_count():
    """Verify that stationary check respects the stationary_count threshold."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    
    hass = FakeHass()
    
    future_time = datetime.now() + timedelta(hours=1)
    gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
    
    hass.states.async_set("device_tracker.smarttag", "home", {
        "latitude": 45.5,
        "longitude": 9.2,
        "gpsUtcDt": gps_timestamp,
        "friendly_name": "SmartTag Scooter",
    })
    
    config = {
        "device_tracker": "device_tracker.smarttag",
        "activation_mode": "position",
        "notifier": "notify.mobile_app",
        "webhook_token": "test_token_position_count",
        "person": "person.test",
        "stationary_minutes": 10,
        "stationary_count": 5,  # Require 5 samples
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Set counter to 3 (below threshold of 5)
    coord._stationary_counter = 3
    
    # Try stationary check - should NOT save (counter too low)
    await coord._stationary_check(45.5, 9.2)
    
    assert coord.saved_latitude is None, "Position should NOT be saved when counter below threshold"
    assert len(hass.notification_calls) == 0, "No notification when threshold not met"
    
    # Now set counter to 5 (meets threshold)
    coord._stationary_counter = 5
    
    # Try again - should save and notify
    await coord._stationary_check(45.5, 9.2)
    
    assert coord.saved_latitude == 45.5, "Position should be saved when threshold met"
    assert len(hass.notification_calls) == 1, "Notification should be sent when threshold met"
    
    print("✓ Position mode correctly respects stationary_count threshold")
