"""Test complete flow for connection mode activation.

This test verifies the entire lifecycle of connection mode:
1. Initial state (alarm disabled, no position)
2. Tag disconnects → alarm activates + position saved
3. Tag connects → alarm deactivates
4. Manual override (start/stop) works
"""
import pytest


@pytest.mark.asyncio
async def test_connection_mode_complete_lifecycle():
    """Test the complete lifecycle of connection mode from start to finish."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    from datetime import datetime, timedelta

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class States:
            def __init__(self):
                self._connected = True
                self._lat = 45.5
                self._lon = 9.2
                
            def set_connection(self, connected):
                self._connected = connected
                
            def get(self, entity_id):
                # Use fresh GPS timestamp
                future_time = datetime.now() + timedelta(hours=1)
                gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
                
                class FakeState:
                    def __init__(self, connected, lat, lon, gps_ts):
                        # Samsung SmartTag format - full payload with result codes
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
                                    "latitude": str(lat),
                                    "longitude": str(lon),
                                    "extra": {"gpsUtcDt": gps_ts},
                                }
                            ],
                            "latitude": lat,
                            "longitude": lon,
                            "gpsUtcDt": gps_ts,
                        }
                        self.state = "home"
                
                return FakeState(self._connected, self._lat, self._lon, gps_timestamp)

        states = States()

    class FakeStore:
        def __init__(self):
            self.data = {}
            
        async def async_load(self):
            return self.data.copy() if self.data else None

        async def async_save(self, data):
            self.data = data.copy()

    hass = FakeHass()

    # Create connection mode coordinator
    config = {
        "device_tracker": "device.tracker_smarttag",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "debug_mode": True,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # STEP 1: Initial state - tag connected, alarm disabled
    print("\n=== STEP 1: Initial state ===")
    assert coord.alarm_active is False, "Alarm should start disabled"
    assert coord.saved_latitude is None, "No position saved initially"
    # last_tag_state starts as "connected" after first event, not at init
    print("✓ Initial state correct: alarm=False, position=None")
    
    # STEP 2: Tag disconnects (user parks vehicle)
    print("\n=== STEP 2: Tag disconnects (parking) ===")
    hass.states.set_connection(False)  # Tag disconnects
    
    # Simulate device_tracker state change event
    class FakeEvent:
        def __init__(self):
            self.data = {
                "entity_id": "device.tracker_smarttag",
                "old_state": hass.states.get("device.tracker_smarttag"),
                "new_state": hass.states.get("device.tracker_smarttag"),
            }
    
    await coord._handle_device_event(FakeEvent())
    
    assert coord.alarm_active is True, "Alarm should activate on disconnect"
    assert coord.saved_latitude == 45.5, "Position should be saved"
    assert coord.saved_longitude == 9.2, "Position should be saved"
    assert coord.last_tag_state == "disconnected", "Tag state should be disconnected"
    assert coord.position_notified is False, "Position not yet notified"
    print(f"✓ Disconnect handled: alarm=True, position=({coord.saved_latitude}, {coord.saved_longitude})")
    
    # STEP 3: Tag connects (user returns to vehicle)
    print("\n=== STEP 3: Tag connects (returning to vehicle) ===")
    hass.states.set_connection(True)  # Tag reconnects
    
    await coord._handle_device_event(FakeEvent())
    
    assert coord.alarm_active is False, "Alarm should deactivate on connect"
    assert coord.saved_latitude == 45.5, "Position should remain saved"
    assert coord.last_tag_state == "connected", "Tag state should be connected"
    print(f"✓ Connect handled: alarm=False, position still saved=({coord.saved_latitude}, {coord.saved_longitude})")
    
    # STEP 4: Manual start override (force alarm while connected)
    print("\n=== STEP 4: Manual start override ===")
    await coord.set_alarm_active(True)
    
    assert coord.alarm_active is True, "Manual start should activate alarm even when connected"
    print("✓ Manual start override works")
    
    # STEP 5: Manual stop override
    print("\n=== STEP 5: Manual stop override ===")
    hass.states.set_connection(False)  # Disconnect again
    await coord._handle_device_event(FakeEvent())
    
    assert coord.alarm_active is True, "Alarm should be active after disconnect"
    
    await coord.set_alarm_active(False)
    
    assert coord.alarm_active is False, "Manual stop should deactivate alarm even when disconnected"
    print("✓ Manual stop override works")
    
    # STEP 6: Verify persistence
    print("\n=== STEP 6: Verify persistence ===")
    saved_data = coord.store.data
    assert saved_data["alarm_active"] is False
    assert saved_data["saved_latitude"] == 45.5
    assert saved_data["saved_longitude"] == 9.2
    assert saved_data["last_tag_state"] == "disconnected"
    print("✓ State persisted correctly")
    
    print("\n=== CONNECTION MODE COMPLETE FLOW: ALL CHECKS PASSED ✓ ===")


@pytest.mark.asyncio
async def test_connection_mode_ignores_manual_mode_logic():
    """Verify that connection mode does NOT trigger on stationary detection."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    from datetime import datetime, timedelta

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class States:
            def get(self, entity_id):
                future_time = datetime.now() + timedelta(hours=1)
                gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
                
                class FakeState:
                    def __init__(self):
                        self.attributes = {
                            "ops": [
                                {
                                    "oprnType": "LOCATION",  # Connected
                                    "oprnResultCode": "1200",
                                    "oprnStsCd": "2800",
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

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    config = {
        "device_tracker": "device.tracker_smarttag",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
        "stationary_minutes": 1,
        "stationary_count": 2,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Simulate multiple stationary position updates (would trigger position mode)
    for i in range(5):
        class FakeEvent:
            def __init__(self):
                self.data = {
                    "entity_id": "device.tracker_smarttag",
                    "old_state": hass.states.get("device.tracker_smarttag"),
                    "new_state": hass.states.get("device.tracker_smarttag"),
                }
        
        await coord._handle_device_event(FakeEvent())
    
    # In connection mode, alarm should NOT activate from stationary detection
    assert coord.alarm_active is False, "Connection mode should ignore stationary detection"
    assert coord.saved_latitude is None, "Position should not be saved from stationary"
    
    print("✓ Connection mode correctly ignores stationary detection logic")
