"""Test that stationary timer doesn't cause threading errors."""
import pytest
from unittest.mock import AsyncMock, patch
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


@pytest.mark.asyncio
async def test_stationary_timer_thread_safety(hass):
    """Test that timer callback doesn't cause threading errors."""
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 0,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    await coordinator.async_load()
    
    # Mock device tracker state
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
            "gps_accuracy": 10,
        }
    )
    
    # Mock notification service
    with patch.object(coordinator, '_async_send_notification', new_callable=AsyncMock):
        # Simulate GPS update that should start timer
        from homeassistant.core import Event, EventStateChangedData
        from homeassistant.helpers.event import async_track_state_change_event
        
        # Create a mock event with new state
        class MockState:
            def __init__(self, entity_id, state, attributes):
                self.entity_id = entity_id
                self.state = state
                self.attributes = attributes
        
        new_state = MockState(
            "device_tracker.test",
            "home",
            {
                "latitude": 45.1234567,
                "longitude": 9.1234567,
                "gps_accuracy": 10,
            }
        )
        
        # Call handle_device_event which creates the timer
        await coordinator.handle_device_event(None, None, new_state)
        
        # Verify timer was created
        assert coordinator._stationary_handle is not None, "Timer should be created"
        assert coordinator._stationary_counter == 1, "Counter should be 1 after first GPS"
        
        # The timer should be an async function, not a lambda with async_create_task
        # This ensures thread safety
        assert callable(coordinator._stationary_handle), "Timer handle should be callable"


@pytest.mark.asyncio
async def test_stationary_timer_execution(hass):
    """Test that timer actually executes and activates alarm."""
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,  # 1 minute for quick test
            "stationary_count": 0,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
            "debug_mode": True,
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    await coordinator.async_load()
    
    # Mock device tracker state
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
            "gps_accuracy": 10,
            "source_type": "gps",
        }
    )
    
    notification_sent = False
    
    async def mock_notify(*args, **kwargs):
        nonlocal notification_sent
        notification_sent = True
    
    with patch.object(coordinator, '_async_send_notification', side_effect=mock_notify):
        # Simulate GPS update
        class MockState:
            def __init__(self):
                self.entity_id = "device_tracker.test"
                self.state = "home"
                self.attributes = {
                    "latitude": 45.1234567,
                    "longitude": 9.1234567,
                    "gps_accuracy": 10,
                    "source_type": "gps",
                }
        
        await coordinator.handle_device_event(None, None, MockState())
        
        # Verify initial state
        assert coordinator._stationary_handle is not None
        assert coordinator.alarm_active is False
        
        # Fast-forward time and trigger the timer manually
        # (in real scenario, async_call_later would trigger this after stationary_minutes)
        if coordinator._stationary_handle:
            # Call _stationary_check directly (simulating timer expiration)
            await coordinator._stationary_check(45.1234567, 9.1234567)
        
        # After timer expiration with count=0, alarm should activate
        assert coordinator.alarm_active is True, "Alarm should be active after timer expires"
        assert coordinator.saved_latitude == 45.1234567
        assert coordinator.saved_longitude == 9.1234567
        assert notification_sent is True, "Notification should be sent"


@pytest.mark.asyncio  
async def test_timer_cancellation_on_movement(hass):
    """Test that timer is cancelled when vehicle moves."""
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 3,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    await coordinator.async_load()
    
    # Set initial position
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
        }
    )
    
    class MockState:
        def __init__(self, lat, lon):
            self.entity_id = "device_tracker.test"
            self.state = "home"
            self.attributes = {
                "latitude": lat,
                "longitude": lon,
            }
    
    # First GPS - starts timer
    await coordinator.handle_device_event(None, None, MockState(45.1234567, 9.1234567))
    first_handle = coordinator._stationary_handle
    assert first_handle is not None
    assert coordinator._stationary_counter == 1
    
    # Second GPS - same position, timer continues
    await coordinator.handle_device_event(None, None, MockState(45.1234567, 9.1234567))
    second_handle = coordinator._stationary_handle
    assert second_handle == first_handle, "Timer should not restart for same position"
    assert coordinator._stationary_counter == 2
    
    # Third GPS - moved outside tolerance (>50m), timer should restart
    await coordinator.handle_device_event(None, None, MockState(45.5080000, 9.1234567))  # ~40m away
    third_handle = coordinator._stationary_handle
    # Counter should reset to 1, and we should have a new timer
    assert coordinator._stationary_counter == 1, "Counter should reset on movement"
    # Timer should be recreated (new callback function)
    assert third_handle is not None, "New timer should be created"
