"""Test early return optimization doesn't break position mode logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator

pytestmark = pytest.mark.asyncio


async def test_early_return_allows_first_event_stationary_count_zero(hass):
    """Test that first event is processed even with unchanged GPS when stationary_count=0."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 1,
        "stationary_count": 0,  # Immediate mode
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Mock timer to avoid event loop issues
    with patch('custom_components.tag_guard_vehicle.coordinator.async_call_later') as mock_timer:
        mock_timer.return_value = MagicMock()
        
        # Verify initial state
        assert coordinator._stationary_candidate is None, "No candidate initially"
        assert coordinator._stationary_counter == 0, "Counter at 0"
        
        # Create event with GPS
        class FakeEvent:
            def __init__(self, gps_ts):
                self.data = {
                    "entity_id": "device_tracker.test",
                    "old_state": None,  # First event, no old_state
                    "new_state": MagicMock(
                        attributes={
                            "ops": [{"extra": {"gpsUtcDt": gps_ts}, "latitude": "45.5", "longitude": "9.2"}],
                            "latitude": 45.5,
                            "longitude": 9.2,
                        }
                    ),
                }
        
        # Process first event
        await coordinator._handle_device_event(FakeEvent("20251109160000"))
        
        # Verify timer started
        assert coordinator._stationary_candidate == (45.5, 9.2), "Candidate should be set"
        assert mock_timer.called, "Timer should have been started"


async def test_early_return_skips_duplicate_gps_when_timer_running(hass):
    """Test that duplicate GPS events are skipped when timer already running."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 1,
        "stationary_count": 0,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Set up initial state (timer already running)
    coordinator._stationary_candidate = (45.5, 9.2)
    coordinator._stationary_counter = 0
    coordinator._stationary_handle = MagicMock()  # Timer running
    
    # Create events with same GPS timestamp
    class FakeEvent:
        def __init__(self, old_gps_ts, new_gps_ts):
            self.data = {
                "entity_id": "device_tracker.test",
                "old_state": MagicMock(
                    attributes={
                        "ops": [{"extra": {"gpsUtcDt": old_gps_ts}, "latitude": "45.5", "longitude": "9.2"}],
                    }
                ),
                "new_state": MagicMock(
                    attributes={
                        "ops": [{"extra": {"gpsUtcDt": new_gps_ts}, "latitude": "45.5", "longitude": "9.2"}],
                        "latitude": 45.5,
                        "longitude": 9.2,
                    }
                ),
            }
    
    # Process event with duplicate GPS timestamp
    with patch('custom_components.tag_guard_vehicle.coordinator._LOGGER') as mock_logger:
        await coordinator._handle_device_event(FakeEvent("20251109160000", "20251109160000"))
        
        # Verify event was skipped (DEBUG log about skipping)
        debug_calls = [call for call in mock_logger.debug.call_args_list if "Skipping event" in str(call)]
        assert len(debug_calls) > 0, "Should have logged skip message"


async def test_early_return_allows_fresh_gps_stationary_count_one(hass):
    """Test that fresh GPS is processed even when timer running (stationary_count=1)."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 1,
        "stationary_count": 1,  # Requires fresh GPS
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Simulate baseline GPS already set
    coordinator._stationary_candidate = (45.5, 9.2)
    coordinator._stationary_counter = 0
    coordinator._last_accepted_gps_timestamp = "20251109160000"
    coordinator._last_processed_gps_timestamp = "20251109160000"
    coordinator._stationary_handle = MagicMock()
    
    # Create event with NEWER GPS timestamp
    class FakeEvent:
        def __init__(self, old_gps_ts, new_gps_ts):
            self.data = {
                "entity_id": "device_tracker.test",
                "old_state": MagicMock(
                    attributes={
                        "ops": [{"extra": {"gpsUtcDt": old_gps_ts}, "latitude": "45.5", "longitude": "9.2"}],
                    }
                ),
                "new_state": MagicMock(
                    attributes={
                        "ops": [{"extra": {"gpsUtcDt": new_gps_ts}, "latitude": "45.5", "longitude": "9.2"}],
                        "latitude": 45.5,
                        "longitude": 9.2,
                    }
                ),
            }
    
    # Process event with fresh GPS
    await coordinator._handle_device_event(FakeEvent("20251109160000", "20251109160100"))
    
    # Verify counter incremented
    assert coordinator._stationary_counter == 1, "Counter should increment with fresh GPS"
    assert coordinator._last_accepted_gps_timestamp == "20251109160100", "Should save new timestamp"


async def test_no_early_return_when_no_old_state(hass):
    """Test that early return is not applied when old_state is None (first event)."""
    config = {
        "device_tracker": "device_tracker.test",
        "webhook_id": "test123",
        "activation_mode": "position",
        "stationary_minutes": 1,
        "stationary_count": 1,
        "tolerance_radius": 200,
        "tag_model": "smarttag2",
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.async_save = AsyncMock()
    
    # Mock timer to avoid event loop issues
    with patch('custom_components.tag_guard_vehicle.coordinator.async_call_later') as mock_timer:
        mock_timer.return_value = MagicMock()
        
        # Create event with no old_state (startup scenario)
        class FakeEvent:
            def __init__(self):
                self.data = {
                    "entity_id": "device_tracker.test",
                    "old_state": None,  # No old state
                    "new_state": MagicMock(
                        attributes={
                            "ops": [{"extra": {"gpsUtcDt": "20251109160000"}, "latitude": "45.5", "longitude": "9.2"}],
                            "latitude": 45.5,
                            "longitude": 9.2,
                        }
                    ),
                }
        
        # Process event
        await coordinator._handle_device_event(FakeEvent())
        
        # Verify baseline was set
        assert coordinator._stationary_candidate == (45.5, 9.2), "Baseline candidate should be set"
        assert coordinator._last_accepted_gps_timestamp == "20251109160000", "Baseline timestamp should be saved"
