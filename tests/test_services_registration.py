"""Verify the integration registers its services and webhook correctly.
"""

import asyncio
import logging
import pytest

from custom_components.vehicle_bt_parking_sentinel import services


class FakeServices:
    def __init__(self):
        self._registry = {}

    def async_register(self, domain, name, func):
        self._registry[(domain, name)] = func

    async def async_call(self, domain, service, data=None):
        # no-op for tests
        return None


class FakeHass:
    def __init__(self):
        self.services = FakeServices()
        self.states = DummyStates()
        self.bus = DummyBus()

    def __getattr__(self, item):
        # provide minimal async_create_task
        if item == "async_create_task":
            return lambda coro: asyncio.get_event_loop().create_task(coro)
        raise AttributeError(item)


class DummyStates:
    def __init__(self):
        self._dict = {}

    def get(self, entity_id):
        return self._dict.get(entity_id)


class DummyBus:
    def __init__(self):
        self._listeners = []

    def async_listen(self, event_type, cb):
        self._listeners.append((event_type, cb))


class DummyCoordinator:
    def __init__(self):
        self._saved = None
        self.position_notified = False

    async def _async_save_position(self, lat, lon):
        self._saved = (lat, lon)

    async def async_save(self):
        return None


@pytest.mark.asyncio
# Test: async_register_services registers save/reset/clear/mute/unmute services
async def test_async_register_services_registers():
    hass = FakeHass()
    coord = DummyCoordinator()
    await services.async_register_services(hass, coord, "device.tracker_1", "notify.test")
    # check that services are registered (manual_trigger was removed - use start with notify_waiting instead)
    assert ("vehicle_bt_parking_sentinel", "save_position") in hass.services._registry
    assert ("vehicle_bt_parking_sentinel", "reset_flags") in hass.services._registry
    assert ("vehicle_bt_parking_sentinel", "clear_persisted") in hass.services._registry
    assert ("vehicle_bt_parking_sentinel", "mute_notifications") in hass.services._registry
    assert ("vehicle_bt_parking_sentinel", "unmute_notifications") in hass.services._registry


@pytest.mark.asyncio
# Test: get_webhook_info returns webhook URL and token and logs the info
async def test_get_webhook_info_logs(monkeypatch, caplog):
    hass = FakeHass()
    coord = DummyCoordinator()
    # register helper services
    await services.async_register_helper_services(hass, coord, "entry1", "secret-token")
    # call get_webhook_info service function
    func = hass.services._registry[("vehicle_bt_parking_sentinel", "get_webhook_info")]
    caplog.set_level(logging.INFO)
    info = await func()
    assert info["token"] == "secret-token"
    assert "/api/webhook/" in info["webhook_url"]
    # ensure log contains the webhook info
    assert any("Webhook info" in rec.getMessage() for rec in caplog.records)
