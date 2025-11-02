"""Test notification in connection mode when tag disconnects."""
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
            self._connected = True
            self._states = {}
            
        def set_connection(self, connected):
            self._connected = connected
        
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
            
            # Otherwise return dynamic state based on connection
            future_time = datetime.now() + timedelta(hours=1)
            gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
            
            class FakeState:
                def __init__(self, connected):
                    if connected:
                        oprn_type = "LOCATION"
                        result_code = "1200"
                        sts_cd = "2800"
                    else:
                        oprn_type = "OFFLINE_LOC"
                        result_code = "1300"
                        sts_cd = "2900"
                        
                    self.attributes = {
                        "ops": [
                            {
                                "oprnType": oprn_type,
                                "oprnResultCode": result_code,
                                "oprnStsCd": sts_cd,
                                "latitude": "45.5",
                                "longitude": "9.2",
                                "extra": {"gpsUtcDt": gps_timestamp},
                            }
                        ],
                        "latitude": 45.5,
                        "longitude": 9.2,
                        "gpsUtcDt": gps_timestamp,
                        "friendly_name": "SmartTag Scooter",
                    }
                    self.state = "home"
            
            return FakeState(self._connected)


class FakeStore:
    def __init__(self):
        self.data = {}
        
    async def async_load(self):
        return self.data.copy() if self.data else None

    async def async_save(self, data):
        self.data = data.copy()


@pytest.mark.asyncio
async def test_connection_mode_sends_notification_on_disconnect():
    """Verify that a notification is sent when tag disconnects in connection mode."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    hass = FakeHass()
    hass.services = FakeHass.Services(hass)

    # Create connection mode coordinator with notifier configured
    config = {
        "device_tracker": "device.tracker_smarttag",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "notifier": "notify.mobile_app",  # Enable notifications!
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Initial state - tag connected
    assert coord.alarm_active is False
    assert len(hass.notification_calls) == 0, "No notifications initially"
    
    # Simulate tag disconnect event
    hass.states.set_connection(False)
    
    class FakeEvent:
        def __init__(self):
            self.data = {
                "entity_id": "device.tracker_smarttag",
                "old_state": hass.states.get("device.tracker_smarttag"),
                "new_state": hass.states.get("device.tracker_smarttag"),
            }
    
    await coord._handle_device_event(FakeEvent())
    
    # Verify alarm activated
    assert coord.alarm_active is True, "Alarm should be activated"
    assert coord.saved_latitude == 45.5, "Position should be saved"
    
    # Verify notification was sent
    assert len(hass.notification_calls) == 1, "One notification should be sent"
    
    notif = hass.notification_calls[0]
    assert notif["domain"] == "notify", "Notification domain should be 'notify'"
    assert notif["service"] == "mobile_app", "Service should match configured notifier"
    assert "title" in notif["data"], "Notification should have a title"
    assert "message" in notif["data"], "Notification should have a message"
    
    # Check content
    title = notif["data"]["title"]
    message = notif["data"]["message"]
    
    assert "Monitoring activated" in title or "Monitoraggio attivato" in title, f"Title should mention activation: {title}"
    # Vehicle name might be "Vehicle" or "SmartTag Scooter" depending on hass.states implementation
    assert "[" in title and "]" in title, "Title should include vehicle name in brackets"
    assert "Tag disconnected" in message or "disconnesso" in message or "Alarm" in message or "Connection" in message, f"Message should mention disconnect/alarm: {message}"
    assert "Mode:" in message or "Modalità:" in message or "Режим:" in message, "Message should mention mode"
    assert "https://maps.google.com" in message, "Message should include map URL"
    
    print(f"\n✓ Notification sent successfully!")
    print(f"  Title: {title}")
    print(f"  Message: {message}")


@pytest.mark.asyncio
async def test_connection_mode_no_notification_without_notifier():
    """Verify that no notification is sent if notifier is not configured."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    from datetime import datetime, timedelta

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}
            self.notification_calls = []

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
            def get(self, entity_id):
                future_time = datetime.now() + timedelta(hours=1)
                gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
                
                class FakeState:
                    def __init__(self):
                        self.attributes = {
                            "ops": [
                                {
                                    "oprnType": "OFFLINE_LOC",
                                    "oprnResultCode": "1300",
                                    "oprnStsCd": "2900",
                                    "latitude": "45.5",
                                    "longitude": "9.2",
                                    "extra": {"gpsUtcDt": gps_timestamp},
                                }
                            ],
                            "latitude": 45.5,
                            "longitude": 9.2,
                            "gpsUtcDt": gps_timestamp,
                        }
                        self.state = "home"
                
                return FakeState()

        states = States()
        services = None

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()
    hass.services = FakeHass.Services(hass)

    # Create connection mode coordinator WITHOUT notifier
    config = {
        "device_tracker": "device.tracker_smarttag",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        # notifier is None/missing
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Simulate disconnect
    class FakeEvent:
        def __init__(self):
            self.data = {
                "entity_id": "device.tracker_smarttag",
                "old_state": hass.states.get("device.tracker_smarttag"),
                "new_state": hass.states.get("device.tracker_smarttag"),
            }
    
    await coord._handle_device_event(FakeEvent())
    
    # Alarm should activate but NO notification sent
    assert coord.alarm_active is True, "Alarm should be activated"
    assert len(hass.notification_calls) == 0, "No notification should be sent without notifier"
    
    print("✓ No notification sent when notifier is not configured (correct behavior)")


@pytest.mark.asyncio
async def test_manual_start_notification_includes_mode():
    """Verify that manual start notification includes mode information."""
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
        "activation_mode": "manual",  # Manual mode
        "notifier": "notify.mobile_app",
        "webhook_token": "test_token_manual_notif",
        "person": "person.test",
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Manually start monitoring
    await coord.set_alarm_active(True, notify_waiting=False)
    
    # Verify notification was sent
    assert len(hass.notification_calls) == 1, "One notification should be sent"
    
    notif = hass.notification_calls[0]
    message = notif["data"]["message"]
    
    # Verify mode is mentioned
    assert "Mode:" in message or "Modalità:" in message, f"Message should include mode: {message}"
    assert "Manual" in message or "Manuale" in message, f"Message should mention Manual mode: {message}"
    
    print(f"\n✓ Manual start notification includes mode!")
    print(f"  Message: {message}")
