"""Test that stop resets position mode state for fresh monitoring."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

pytestmark = pytest.mark.asyncio


async def test_stop_resets_position_mode_state(hass):
    """Test that stopping alarm resets position mode tracking variables."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 5,
        "stationary_count": 1,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    
    # Mock async_save to avoid storage issues in tests
    coordinator.async_save = AsyncMock()
    
    # Simulate position mode has been running and has state
    coordinator._stationary_counter = 2
    coordinator._stationary_candidate = (45.5, 9.2)
    coordinator._stationary_candidate_gpsUtcDt = "20251107000000"
    coordinator._last_accepted_gps_timestamp = "20251107000000"
    coordinator._last_processed_gps_timestamp = "20251107000100"
    coordinator._stationary_handle = MagicMock()  # Mock timer handle
    
    # Initially alarm is active (parked state)
    coordinator.alarm_active = True
    
    # Stop the alarm (like webhook stop)
    await coordinator.set_alarm_active(False)
    
    # Verify all position mode state is reset
    assert coordinator._stationary_counter == 0, "Counter should be reset to 0"
    assert coordinator._stationary_candidate is None, "Candidate should be reset to None"
    assert coordinator._stationary_candidate_gpsUtcDt is None, "Candidate GPS timestamp should be reset"
    assert coordinator._last_accepted_gps_timestamp is None, "Last accepted GPS timestamp should be reset"
    assert coordinator._last_processed_gps_timestamp is None, "Last processed GPS timestamp should be reset"
    assert coordinator._stationary_handle is None, "Timer should be cancelled"
    assert not coordinator.alarm_active, "Alarm should be inactive"


async def test_stop_cancels_pending_timer(hass):
    """Test that stopping alarm cancels any pending stationary timer."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 5,
        "stationary_count": 1,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    coordinator.alarm_active = True
    
    # Mock timer handle with callable
    timer_cancel_mock = MagicMock()
    coordinator._stationary_handle = timer_cancel_mock
    
    # Stop the alarm
    await coordinator.set_alarm_active(False)
    
    # Verify timer was cancelled
    timer_cancel_mock.assert_called_once()
    assert coordinator._stationary_handle is None


async def test_position_mode_restarts_fresh_after_stop(hass):
    """Test that position mode starts fresh monitoring after stop (new baseline GPS)."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 5,
        "stationary_count": 1,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Simulate alarm was active with old position data
    coordinator.alarm_active = True
    coordinator._stationary_counter = 3
    coordinator._stationary_candidate = (45.5, 9.2)
    coordinator._last_accepted_gps_timestamp = "20251107000000"  # Old baseline
    
    # Stop the alarm
    await coordinator.set_alarm_active(False)
    
    # Verify state is reset
    assert coordinator._stationary_counter == 0
    assert coordinator._stationary_candidate is None
    assert coordinator._last_accepted_gps_timestamp is None
    
    # Now simulate a new GPS update arrives (position mode should restart)
    # The baseline GPS timestamp check should accept the new GPS as baseline
    # (This is tested implicitly - after reset, _last_accepted_gps_timestamp is None,
    # so the next GPS will be treated as baseline and saved without incrementing counter)


async def test_stop_only_resets_when_alarm_was_active(hass):
    """Test that stop only resets state if alarm was previously active."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 5,
        "stationary_count": 1,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Set some state
    coordinator._stationary_counter = 2
    coordinator._stationary_candidate = (45.5, 9.2)
    coordinator._last_accepted_gps_timestamp = "20251107000000"
    
    # Alarm is already inactive
    coordinator.alarm_active = False
    
    # Call set_alarm_active(False) again (redundant stop)
    await coordinator.set_alarm_active(False)
    
    # State should NOT be reset (because alarm wasn't active before)
    # This ensures we don't reset during normal position mode monitoring
    assert coordinator._stationary_counter == 2, "Counter should not be reset when alarm wasn't active"
    assert coordinator._stationary_candidate == (45.5, 9.2), "Candidate should not be reset"
    assert coordinator._last_accepted_gps_timestamp == "20251107000000", "Timestamp should not be reset"
