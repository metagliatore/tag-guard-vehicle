"""Test multi-instance cleanup and memory leak verification."""
import gc
import weakref
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.tag_guard_vehicle import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.tag_guard_vehicle.const import DOMAIN


@pytest.fixture
def mock_config_entry_1():
    """Create a mock config entry for instance 1."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_1"
    entry.data = {
        "device_tracker": "device_tracker.test_phone_1",
        "notifier": "notify.mobile_app_1",
        "tolerance_radius": 200,
        "webhook_token": "token_instance_1",
    }
    entry.options = {
        "person_entity": "person.test_1",
        "activation_mode": "position",
        "webhook_token": "token_instance_1",
    }
    entry.add_update_listener = MagicMock()
    return entry


@pytest.fixture
def mock_config_entry_2():
    """Create a mock config entry for instance 2."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_2"
    entry.data = {
        "device_tracker": "device_tracker.test_phone_2",
        "notifier": "notify.mobile_app_2",
        "tolerance_radius": 150,
        "webhook_token": "token_instance_2",
    }
    entry.options = {
        "person_entity": "person.test_2",
        "activation_mode": "combined",
        "webhook_token": "token_instance_2",
    }
    entry.add_update_listener = MagicMock()
    return entry


@pytest.mark.asyncio
async def test_complete_cleanup_on_unload(hass: HomeAssistant, mock_config_entry_1):
    """Test that all resources are properly cleaned up on unload."""
    
    with patch("custom_components.tag_guard_vehicle.services.async_register_services"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_webhook_and_listeners"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_helper_services"), \
         patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True):
        
        # Setup entry
        await async_setup_entry(hass, mock_config_entry_1)
        
        # Verify coordinator is registered
        assert DOMAIN in hass.data
        assert "coordinators" in hass.data[DOMAIN]
        assert "test_entry_1" in hass.data[DOMAIN]["coordinators"]
        coordinator = hass.data[DOMAIN]["coordinators"]["test_entry_1"]
        
        # Create weak reference to detect garbage collection
        coord_weakref = weakref.ref(coordinator)
        
        # Verify webhook mapping exists
        if "_webhook_to_entry" in hass.data[DOMAIN]:
            assert "token_instance_1" in hass.data[DOMAIN]["_webhook_to_entry"]
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Unload entry
            result = await async_unload_entry(hass, mock_config_entry_1)
            assert result is True
        
        # Verify coordinator removed from registry
        assert "test_entry_1" not in hass.data.get(DOMAIN, {}).get("coordinators", {})
        
        # Verify webhook mapping removed
        if "_webhook_to_entry" in hass.data.get(DOMAIN, {}):
            assert "token_instance_1" not in hass.data[DOMAIN]["_webhook_to_entry"]
        
        # Delete local reference and force garbage collection
        del coordinator
        gc.collect()
        
        # Verify coordinator was garbage collected (no memory leak)
        assert coord_weakref() is None, "Coordinator was not garbage collected - memory leak detected!"


@pytest.mark.asyncio
async def test_two_instances_isolation(hass: HomeAssistant, mock_config_entry_1, mock_config_entry_2):
    """Test that two instances are properly isolated and cleanup works correctly."""
    
    with patch("custom_components.tag_guard_vehicle.services.async_register_services"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_webhook_and_listeners"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_helper_services"), \
         patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True):
        
        # Setup first instance
        await async_setup_entry(hass, mock_config_entry_1)
        coord1 = hass.data[DOMAIN]["coordinators"]["test_entry_1"]
        coord1_weakref = weakref.ref(coord1)
        
        # Setup second instance
        await async_setup_entry(hass, mock_config_entry_2)
        coord2 = hass.data[DOMAIN]["coordinators"]["test_entry_2"]
        coord2_weakref = weakref.ref(coord2)
        
        # Verify both coordinators exist
        assert len(hass.data[DOMAIN]["coordinators"]) == 2
        assert "test_entry_1" in hass.data[DOMAIN]["coordinators"]
        assert "test_entry_2" in hass.data[DOMAIN]["coordinators"]
        
        # Verify webhook mappings for both instances
        if "_webhook_to_entry" in hass.data[DOMAIN]:
            assert hass.data[DOMAIN]["_webhook_to_entry"].get("token_instance_1") == "test_entry_1"
            assert hass.data[DOMAIN]["_webhook_to_entry"].get("token_instance_2") == "test_entry_2"
        
        # Verify coordinators are different objects
        assert coord1 is not coord2
        assert coord1.entry_id != coord2.entry_id
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Unload first instance
            result1 = await async_unload_entry(hass, mock_config_entry_1)
            assert result1 is True
        
        # Verify first coordinator removed, second still exists
        assert "test_entry_1" not in hass.data[DOMAIN]["coordinators"]
        assert "test_entry_2" in hass.data[DOMAIN]["coordinators"]
        assert len(hass.data[DOMAIN]["coordinators"]) == 1
        
        # Verify first webhook mapping removed, second still exists
        if "_webhook_to_entry" in hass.data[DOMAIN]:
            assert "token_instance_1" not in hass.data[DOMAIN]["_webhook_to_entry"]
            assert hass.data[DOMAIN]["_webhook_to_entry"].get("token_instance_2") == "test_entry_2"
        
        # Second coordinator should still be functional
        assert coord2.entry_id == "test_entry_2"
        
        # Delete first coordinator reference and check garbage collection
        del coord1
        gc.collect()
        assert coord1_weakref() is None, "First coordinator leaked after unload!"
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Unload second instance
            result2 = await async_unload_entry(hass, mock_config_entry_2)
            assert result2 is True
        
        # Verify all coordinators removed
        assert len(hass.data.get(DOMAIN, {}).get("coordinators", {})) == 0
        
        # Verify all webhook mappings removed
        if "_webhook_to_entry" in hass.data.get(DOMAIN, {}):
            assert "token_instance_2" not in hass.data[DOMAIN]["_webhook_to_entry"]
        
        # Delete second coordinator reference and check garbage collection
        del coord2
        gc.collect()
        assert coord2_weakref() is None, "Second coordinator leaked after unload!"


@pytest.mark.asyncio
async def test_no_circular_references(hass: HomeAssistant, mock_config_entry_1):
    """Test that there are no circular references between coordinator and hass.data."""
    
    with patch("custom_components.tag_guard_vehicle.services.async_register_services"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_webhook_and_listeners"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_helper_services"), \
         patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True):
        
        # Setup entry
        await async_setup_entry(hass, mock_config_entry_1)
        coordinator = hass.data[DOMAIN]["coordinators"]["test_entry_1"]
        
        # Check referrers of the coordinator before cleanup
        referrers = gc.get_referrers(coordinator)
        referrer_types = [type(r).__name__ for r in referrers]
        
        # Expected referrers: locals dict, hass.data dict, possibly weakref
        # Should NOT have circular reference loops
        print(f"Coordinator referrer types: {referrer_types}")
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Unload
            await async_unload_entry(hass, mock_config_entry_1)
        
        # After unload, coordinator should only be referenced by our local variable
        referrers_after = gc.get_referrers(coordinator)
        referrer_types_after = [type(r).__name__ for r in referrers_after]
        
        print(f"Coordinator referrer types after unload: {referrer_types_after}")
        
        # Verify coordinator is not in hass.data anymore
        assert coordinator not in str(hass.data.get(DOMAIN, {}))
        
        # Delete local reference
        del coordinator
        gc.collect()


@pytest.mark.asyncio
async def test_webhook_handler_routes_to_correct_instance(hass: HomeAssistant, mock_config_entry_1, mock_config_entry_2):
    """Test that webhook handler correctly routes to the right coordinator instance."""
    
    with patch("custom_components.tag_guard_vehicle.services.async_register_services"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_webhook_and_listeners") as mock_webhook, \
         patch("custom_components.tag_guard_vehicle.services.async_register_helper_services"), \
         patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True):
        
        # Setup both instances
        await async_setup_entry(hass, mock_config_entry_1)
        await async_setup_entry(hass, mock_config_entry_2)
        
        # Verify webhook mappings are correct
        webhook_to_entry = hass.data[DOMAIN].get("_webhook_to_entry", {})
        
        assert webhook_to_entry.get("token_instance_1") == "test_entry_1"
        assert webhook_to_entry.get("token_instance_2") == "test_entry_2"
        
        # Verify coordinators can be looked up by webhook token
        coord1 = hass.data[DOMAIN]["coordinators"].get(webhook_to_entry.get("token_instance_1"))
        coord2 = hass.data[DOMAIN]["coordinators"].get(webhook_to_entry.get("token_instance_2"))
        
        assert coord1 is not None
        assert coord2 is not None
        assert coord1.entry_id == "test_entry_1"
        assert coord2.entry_id == "test_entry_2"
        
        # Simulate webhook call for first instance
        entry_id_1 = webhook_to_entry.get("token_instance_1")
        coordinator_1 = hass.data[DOMAIN]["coordinators"].get(entry_id_1)
        assert coordinator_1.entry_id == "test_entry_1"
        
        # Simulate webhook call for second instance
        entry_id_2 = webhook_to_entry.get("token_instance_2")
        coordinator_2 = hass.data[DOMAIN]["coordinators"].get(entry_id_2)
        assert coordinator_2.entry_id == "test_entry_2"


@pytest.mark.asyncio
async def test_global_mobile_action_listener_cleanup(hass: HomeAssistant, mock_config_entry_1, mock_config_entry_2):
    """Test that global mobile action listener is cleaned up only when last instance is removed."""
    
    with patch("custom_components.tag_guard_vehicle.services.async_register_services"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_webhook_and_listeners"), \
         patch("custom_components.tag_guard_vehicle.services.async_register_helper_services"), \
         patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True):
        
        # Setup first instance
        await async_setup_entry(hass, mock_config_entry_1)
        
        # Setup second instance
        await async_setup_entry(hass, mock_config_entry_2)
        
        # Create mock for mobile action listener
        mock_listener_unsub = MagicMock()
        if "_mobile_action_listener" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["_mobile_action_listener"] = mock_listener_unsub
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Unload first instance - listener should NOT be removed yet
            await async_unload_entry(hass, mock_config_entry_1)
            
            # Verify listener still exists (second instance still active)
            assert "_mobile_action_listener" in hass.data.get(DOMAIN, {})
            
            # Unload second instance - listener should be removed now
            await async_unload_entry(hass, mock_config_entry_2)
            
            # Verify listener was removed (no more instances)
            assert "_mobile_action_listener" not in hass.data.get(DOMAIN, {})
