"""Test to verify require_fresh_position behavior end-to-end"""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_save_with_fresh_gps_saves_immediately():
    """Test that save with fresh GPS saves immediately."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass

    class FakeHass:
        def __init__(self):
            self.services = self
            self.states_map = {}

        def states_get(self, entity_id):
            return self.states_map.get(entity_id)

        class States:
            def __init__(self, parent):
                self.parent = parent
            def get(self, entity_id):
                return self.parent.states_map.get(entity_id)

        @property
        def states(self):
            return self.States(self)

        async def async_call(self, domain, service, data):
            pass

    class FakeState:
        def __init__(self, fresh_gps=True):
            # Create a fresh GPS timestamp (future timestamp)
            future_time = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            future_timestamp = int(future_time) + 100  # 100 seconds in the future (format-compatible)
            
            if fresh_gps:
                gps_timestamp = str(future_timestamp)
            else:
                # Old GPS (past timestamp)
                gps_timestamp = "20200101120000"
            
            self.attributes = {
                "latitude": 45.123,
                "longitude": 9.456,
                "ops": [{"extra": {"gpsUtcDt": gps_timestamp, "locationType": "gps"}}],
                "last_seen": "2024-01-01T12:00:00"
            }
    
    # Test 1: Fresh GPS - should save immediately
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "notifier": "test_notify",
        "options": {}
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()  # Use FakeStore to avoid hass.state errors
    hass.states_map["device_tracker.test"] = FakeState(fresh_gps=True)

    # Call the method with require_fresh_position=True
    await coordinator._async_save_position_with_freshness_check(
        45.123, 9.456, require_fresh_position=True, reason="save"
    )

    # Should have saved immediately
    assert coordinator.saved_latitude == 45.123
    assert coordinator.saved_longitude == 9.456
    assert coordinator._awaiting_activation_save == False
    print("✅ Test 1 PASSED: Fresh GPS saved immediately")


@pytest.mark.asyncio
async def test_save_with_stale_gps_starts_monitoring():
    """Test that save with stale GPS starts monitoring."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass

    class FakeHass:
        def __init__(self):
            self.services = self
            self.states_map = {}
            self.notification_sent = False
            
        def states_get(self, entity_id):
            return self.states_map.get(entity_id)
        
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
                self.notification_sent = True
                print(f"📧 Notification sent: {data.get('title')} - {data.get('message')}")
    
    class FakeState:
        def __init__(self):
            # Old GPS timestamp (past)
            self.attributes = {
                "latitude": 45.123,
                "longitude": 9.456,
                "ops": [{"extra": {"gpsUtcDt": "20200101120000", "locationType": "gps"}}],
                "last_seen": "2024-01-01T12:00:00"
            }
    
    # Test 2: Stale GPS - should start monitoring
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "notifier": "test_notify",
        "options": {}
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()  # Use FakeStore to avoid hass.state errors
    coordinator.notifier = "notify.test"  # Set notifier for notifications
    hass.states_map["device_tracker.test"] = FakeState()

    # Call the method with require_fresh_position=True and notify_waiting=True
    await coordinator._async_save_position_with_freshness_check(
        45.123, 9.456, require_fresh_position=True, notify_waiting=True, reason="save"
    )

    # Verify monitoring was started
    assert coordinator.saved_latitude is None  # Should NOT have saved yet
    assert coordinator._awaiting_activation_save == True  # Should be waiting
    assert coordinator._activation_time_str is not None
    assert hass.notification_sent == True  # Should have sent notification
    print("✅ Test 2 PASSED: Stale GPS started monitoring")


@pytest.mark.asyncio
async def test_save_with_require_false_saves_immediately():
    """Test that save with require_fresh_position=False saves immediately regardless."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

    class FakeStore:
        async def async_load(self):
            return None
        
        async def async_save(self, data):
            pass

    class FakeHass:
        def __init__(self):
            self.services = self

        async def async_call(self, domain, service, data):
            pass

    # Test 3: require_fresh_position=False - should always save immediately
    hass = FakeHass()
    config = {
        "device_tracker": "device_tracker.test",
        "tag_model": "samsung_smarttag2",
        "notifier": "test_notify",
        "options": {}
    }

    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()  # Use FakeStore to avoid hass.state errors

    # Call the method with require_fresh_position=False (legacy behavior)
    await coordinator._async_save_position_with_freshness_check(
        45.123, 9.456, require_fresh_position=False, reason="save"
    )    # Verify position was saved immediately (no GPS check)
    assert coordinator.saved_latitude == 45.123
    assert coordinator.saved_longitude == 9.456
    assert coordinator._awaiting_activation_save == False
    print("✅ Test 3 PASSED: require_fresh_position=False saved immediately")


if __name__ == "__main__":
    import asyncio
    
    print("🧪 Running require_fresh_position behavior tests...\n")
    
    # Run tests
    asyncio.run(test_save_with_fresh_gps_saves_immediately())
    asyncio.run(test_save_with_stale_gps_starts_monitoring())
    asyncio.run(test_save_with_require_false_saves_immediately())
    
    print("\n✅ ALL TESTS PASSED - Behavior is correct!")
