"""Test notify_waiting parameter for save action"""
import pytest
from unittest.mock import MagicMock
from aiohttp import web


@pytest.mark.asyncio
async def test_webhook_save_with_notify_waiting_false_default():
    """Test that save action defaults to notify_waiting=False."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeState:
        def __init__(self):
            self.attributes = {"latitude": 45.789, "longitude": 9.123}

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return FakeState()

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False
            self.saved_latitude = None
            self.saved_longitude = None
            self.notify_waiting_called_with = None

        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = lat
            self.saved_longitude = lon

        async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
            # Track what parameter was passed
            self.notify_waiting_called_with = notify_waiting
            await self._async_save_position(lat, lon, reason=reason)

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Test 1: Default behavior (no notify_waiting parameter)
    request1 = MagicMock(spec=web.Request)
    request1.method = "POST"
    request1.query = {}
    async def fake_json1():
        return {"action": "save"}
    request1.json = fake_json1

    coordinator1 = FakeCoordinator()
    response1 = await handle_webhook_impl(coordinator1.hass, coordinator1, "device.tracker_test", request1)
    
    assert response1.status == 200
    assert coordinator1.notify_waiting_called_with == False  # Default

    # Test 2: Explicit notify_waiting=False
    request2 = MagicMock(spec=web.Request)
    request2.method = "POST"
    request2.query = {}
    async def fake_json2():
        return {"action": "save", "notify_waiting": False}
    request2.json = fake_json2

    coordinator2 = FakeCoordinator()
    response2 = await handle_webhook_impl(coordinator2.hass, coordinator2, "device.tracker_test", request2)
    
    assert response2.status == 200
    assert coordinator2.notify_waiting_called_with == False

    # Test 3: Explicit notify_waiting=True
    request3 = MagicMock(spec=web.Request)
    request3.method = "POST"
    request3.query = {}
    async def fake_json3():
        return {"action": "save", "notify_waiting": True}
    request3.json = fake_json3

    coordinator3 = FakeCoordinator()
    response3 = await handle_webhook_impl(coordinator3.hass, coordinator3, "device.tracker_test", request3)
    
    assert response3.status == 200
    assert coordinator3.notify_waiting_called_with == True


@pytest.mark.asyncio
async def test_webhook_save_with_both_parameters():
    """Test save with both require_fresh_position and notify_waiting."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeState:
        def __init__(self):
            self.attributes = {"latitude": 45.789, "longitude": 9.123}

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return FakeState()

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.require_fresh_called_with = None
            self.notify_waiting_called_with = None

        async def _async_save_position(self, lat, lon, **kwargs):
            pass

        async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
            self.require_fresh_called_with = require_fresh_position
            self.notify_waiting_called_with = notify_waiting
            await self._async_save_position(lat, lon, reason=reason)

        async def async_save(self):
            pass

    # Test with both parameters
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}
    async def fake_json():
        return {"action": "save", "require_fresh_position": False, "notify_waiting": True}
    request.json = fake_json

    coordinator = FakeCoordinator()
    response = await handle_webhook_impl(coordinator.hass, coordinator, "device.tracker_test", request)
    
    assert response.status == 200
    assert coordinator.require_fresh_called_with == False
    assert coordinator.notify_waiting_called_with == True
