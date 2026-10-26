"""Test that stationary_count=0 is handled correctly."""
import pytest
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


@pytest.mark.asyncio
async def test_stationary_count_zero_in_options(hass):
    """Test that stationary_count=0 is read correctly from options."""
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 0,  # Should be preserved as 0, not changed to 1 or 3
            "tolerance_radius": 200,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    
    # Check that stationary_count is 0, not the default 3 or changed to 1
    assert coordinator.stationary_count == 0, f"Expected stationary_count=0, got {coordinator.stationary_count}"
    assert coordinator.stationary_minutes == 1


@pytest.mark.asyncio
async def test_stationary_count_default_when_missing(hass):
    """Test that stationary_count defaults to 3 when not provided."""
    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 10,
            # stationary_count not provided
            "tolerance_radius": 200,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    
    # Should use default value of 2
    assert coordinator.stationary_count == 2
    assert coordinator.stationary_minutes == 10


@pytest.mark.asyncio
async def test_stationary_count_in_config_not_options(hass):
    """Test backwards compatibility: read from config if not in options."""
    config = {
        "device_tracker": "device_tracker.test",
        "stationary_count": 5,  # In config, not options (old format)
        "stationary_minutes": 15,
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "tolerance_radius": 200,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    
    # Should read from config as fallback
    assert coordinator.stationary_count == 5
    assert coordinator.stationary_minutes == 15


@pytest.mark.asyncio
async def test_stationary_count_options_override_config(hass):
    """Test that options override config values."""
    config = {
        "device_tracker": "device_tracker.test",
        "stationary_count": 5,  # In config (old value)
        "stationary_minutes": 15,
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_count": 0,  # In options (new value, should win)
            "stationary_minutes": 1,
            "tolerance_radius": 200,
            "webhook_token": "test_token",
        }
    }
    
    coordinator = VehicleCoordinator(hass, "test_entry", config)
    
    # Options should override config
    assert coordinator.stationary_count == 0, f"Expected 0 from options, got {coordinator.stationary_count}"
    assert coordinator.stationary_minutes == 1
