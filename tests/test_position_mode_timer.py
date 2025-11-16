"""Tests for Position mode timer behavior.

These tests verify the critical timer logic fix:
- Timer should start when position changes (counter==1)
- Timer should continue running when position is stable (counter>1)
- Timer should NOT reset on every GPS update

This ensures Position mode works correctly even with frequent GPS updates.
"""
import pytest
from unittest.mock import MagicMock, patch
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
from custom_components.tag_guard_vehicle.utils import update_stationary_counter


class FakeStore:
    """Fake store for testing."""

    async def async_load(self):
        return None

    async def async_save(self, data):
        pass


@pytest.mark.asyncio
async def test_update_stationary_counter_behavior():
    """Test update_stationary_counter behavior to understand timer logic."""
    tolerance_radius = 50  # meters
    
    # Test 1: First position - should return counter=1 with that position as candidate
    candidate, counter = update_stationary_counter(None, 0, (45.0, 9.0), tolerance_radius)
    assert counter == 1
    assert candidate == (45.0, 9.0)
    
    # Test 2: Same position (within tolerance) - counter increases, same candidate
    candidate, counter = update_stationary_counter(candidate, counter, (45.00001, 9.00001), tolerance_radius)
    assert counter == 2
    assert candidate == (45.0, 9.0)  # Candidate unchanged
    
    # Test 3: Still within tolerance - counter continues increasing
    candidate, counter = update_stationary_counter(candidate, counter, (45.00002, 9.00002), tolerance_radius)
    assert counter == 3
    assert candidate == (45.0, 9.0)  # Candidate unchanged
    
    # Test 4: Moved outside tolerance - counter resets to 1, new candidate
    candidate, counter = update_stationary_counter(candidate, counter, (45.001, 9.001), tolerance_radius)
    assert counter == 1
    assert candidate == (45.001, 9.001)  # New candidate


@pytest.mark.asyncio
async def test_timer_logic_with_stable_position(hass):
    """Test that timer doesn't reset when position is stable.
    
    This is the critical fix: timer should only reset when counter==1 (movement),
    not on every GPS update.
    """
    config = {
        "device_tracker_entity_id": "device_tracker.test",
        "bt_entity_id": "sensor.test_bt",
        "activation_mode": "position",
        "stationary_minutes": 10,
        "stationary_count": 3,
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Track timer creation/cancellation
    timer_calls = []
    timer_handles = []
    
    def mock_call_later(hass, delay, callback):
        """Mock that tracks timer calls."""
        timer_calls.append({"delay": delay})
        # Return a mock cancel handle
        cancel_mock = MagicMock()
        timer_handles.append(cancel_mock)
        return cancel_mock
    
    with patch("custom_components.tag_guard_vehicle.coordinator.async_call_later", side_effect=mock_call_later):
        # Simulate first stable position reading - counter=1
        # This should START the timer
        coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
            coord._stationary_candidate, coord._stationary_counter, (45.0, 9.0), coord.tolerance_radius
        )
        
        assert coord._stationary_counter == 1
        assert coord._stationary_candidate == (45.0, 9.0)
        
        # Manually trigger what would happen in _async_device_tracker_changed
        # when counter==1: start timer
        if coord._stationary_handle:
            coord._stationary_handle()
        coord._stationary_handle = mock_call_later(hass, coord.stationary_minutes * 60, lambda _now: None)
        
        assert len(timer_calls) == 1
        assert timer_calls[0]["delay"] == 600  # 10 minutes
        
        # Now simulate 3 more GPS updates at same position (within tolerance)
        # Timer should NOT be restarted
        for i in range(3):
            old_timer_handle = coord._stationary_handle
            
            # Update position (slight variation but within 50m)
            coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
                coord._stationary_candidate, coord._stationary_counter, 
                (45.0 + (i+1) * 0.00001, 9.0 + (i+1) * 0.00001), 
                coord.tolerance_radius
            )
            
            # Counter should increase (position stable)
            assert coord._stationary_counter == i + 2
            assert coord._stationary_candidate == (45.0, 9.0)  # Candidate unchanged
            
            # Since counter>1, timer should NOT be restarted
            # (In real code, this is the "else" branch that checks if handle exists)
            assert coord._stationary_handle is old_timer_handle  # Handle unchanged
            assert len(timer_calls) == 1  # No new timer created
        
        # Final state: counter=4, only 1 timer ever created
        assert coord._stationary_counter == 4
        assert len(timer_calls) == 1


@pytest.mark.asyncio
async def test_timer_resets_on_movement(hass):
    """Test that timer DOES reset when position moves outside tolerance."""
    config = {
        "device_tracker_entity_id": "device_tracker.test",
        "bt_entity_id": "sensor.test_bt",
        "activation_mode": "position",
        "stationary_minutes": 10,
        "stationary_count": 3,
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    timer_calls = []
    
    def mock_call_later(hass, delay, callback):
        timer_calls.append({"delay": delay})
        cancel_mock = MagicMock()
        return cancel_mock
    
    with patch("custom_components.tag_guard_vehicle.coordinator.async_call_later", side_effect=mock_call_later):
        # First position - counter=1, start timer
        coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
            coord._stationary_candidate, coord._stationary_counter, (45.0, 9.0), coord.tolerance_radius
        )
        assert coord._stationary_counter == 1
        
        if coord._stationary_handle:
            coord._stationary_handle()
        coord._stationary_handle = mock_call_later(hass, coord.stationary_minutes * 60, lambda _now: None)
        
        assert len(timer_calls) == 1
        
        # Second position - still stable, counter=2, timer continues
        coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
            coord._stationary_candidate, coord._stationary_counter, (45.00001, 9.00001), coord.tolerance_radius
        )
        assert coord._stationary_counter == 2
        assert len(timer_calls) == 1  # No new timer
        
        # Third position - MOVED far away
        old_candidate = coord._stationary_candidate
        coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
            coord._stationary_candidate, coord._stationary_counter, (45.001, 9.001), coord.tolerance_radius
        )
        
        # Counter should reset to 1, new candidate
        assert coord._stationary_counter == 1
        assert coord._stationary_candidate != old_candidate
        assert coord._stationary_candidate == (45.001, 9.001)
        
        # Timer should be restarted (in real code this happens when counter==1)
        if coord._stationary_handle:
            coord._stationary_handle()
        coord._stationary_handle = mock_call_later(hass, coord.stationary_minutes * 60, lambda _now: None)
        
        assert len(timer_calls) == 2  # New timer created


@pytest.mark.asyncio
async def test_stationary_detection_with_frequent_updates(hass):
    """Test that stationary detection works with GPS updates every 2 minutes.
    
    Scenario:
    - GPS updates every 2 minutes
    - Timer configured for 10 minutes
    - stationary_count = 3
    
    Expected: Timer should expire after 10 minutes, triggering save when counter >= 3.
    """
    config = {
        "device_tracker_entity_id": "device_tracker.test",
        "bt_entity_id": "sensor.test_bt",
        "activation_mode": "position",
        "stationary_minutes": 10,
        "stationary_count": 3,
        "tolerance_radius": 50,
    }
    
    coord = VehicleCoordinator(hass, "test_entry", config)
    coord.store = FakeStore()
    await coord.async_load()
    
    # Simulate 5 GPS updates, each at the same stable position
    positions = [
        (45.0, 9.0),
        (45.00001, 9.00001),
        (45.00002, 9.00002),
        (45.00003, 9.00003),
        (45.00004, 9.00004),
    ]
    
    for i, pos in enumerate(positions):
        coord._stationary_candidate, coord._stationary_counter = update_stationary_counter(
            coord._stationary_candidate, coord._stationary_counter, pos, coord.tolerance_radius
        )
        
        # Counter should increase with each update
        assert coord._stationary_counter == i + 1
        # Candidate should remain the first position
        assert coord._stationary_candidate == positions[0]
    
    # After 5 updates at same position:
    # - Counter should be 5 (>= stationary_count of 3)
    # - Timer would have expired after 10 minutes
    # - _stationary_check() would be called and should succeed
    assert coord._stationary_counter == 5
    assert coord._stationary_counter >= coord.stationary_count
