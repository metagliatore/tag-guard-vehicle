import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import web

from custom_components.tag_guard_vehicle.const import DOMAIN, DEFAULT_WEBHOOK_ID
from custom_components.tag_guard_vehicle import services


class FakeCall:
    def __init__(self, data=None):
        self.data = data or {}


class FakeState:
    def __init__(self, attrs=None):
        self.attributes = attrs or {}


class FakeStates:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def get(self, entity_id):
        return self.mapping.get(entity_id)


class FakeBus:
    def __init__(self):
        self.listeners = []

    def async_listen(self, event_type, cb):
        self.listeners.append((event_type, cb))
        return lambda: None


class FakeServicesRegistry:
    def __init__(self):
        self._registry = {}
        self._existing = set()

    def async_register(self, domain, name, func):
        self._registry[(domain, name)] = func

    def has_service(self, domain, name):
        return (domain, name) in self._existing

    async def async_call(self, domain, service, data=None):
        return None


class FakeCoordinator:
    def __init__(self, entry_id="entry_1", device_tracker="device_tracker.test", notifier="mobile_app"):
        self.entry_id = entry_id
        self.config = {
            "device_tracker": device_tracker,
            "notifier": notifier,
            "options": {"webhook_token": "tok-1"},
        }
        self.alarm_active = False
        self.position_notified = False
        self.saved_latitude = 45.5
        self.saved_longitude = 9.2
        self.saved_gpsUtcDt = "ts"
        self.saved_location_type = "basic"
        self.saved_last_seen = "seen"
        self.last_tag_state = "connected"
        self.saved_calls = []
        self.set_alarm_calls = []

    async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
        self.saved_calls.append((lat, lon, require_fresh_position, notify_waiting, reason))

    async def async_save(self):
        return None

    async def set_alarm_active(self, active, notify_waiting=False):
        self.alarm_active = bool(active)
        self.set_alarm_calls.append((active, notify_waiting))


class FakeHass:
    def __init__(self, states=None):
        self.states = FakeStates(states)
        self.services = FakeServicesRegistry()
        self.bus = FakeBus()
        self.data = {DOMAIN: {"coordinators": {}}}

    def async_create_task(self, coro):
        return asyncio.get_event_loop().create_task(coro)


@pytest.mark.asyncio
async def test_get_coordinators_for_call_branches():
    hass = FakeHass()
    c1 = FakeCoordinator(entry_id="entry_1", device_tracker="device_tracker.a", notifier="n1")
    c2 = FakeCoordinator(entry_id="entry_2", device_tracker="device_tracker.b", notifier="n2")
    hass.data[DOMAIN]["coordinators"] = {"entry_1": c1, "entry_2": c2}

    all_res = services._get_coordinators_for_call(hass, None)
    assert len(all_res) == 2

    one_res = services._get_coordinators_for_call(hass, FakeCall({"config_entry": "entry_1"}))
    assert len(one_res) == 1
    assert one_res[0][0] is c1

    missing = services._get_coordinators_for_call(hass, FakeCall({"config_entry": "missing"}))
    assert missing == []

    class NoDataHass:
        pass

    fb = services._get_coordinators_for_call(NoDataHass(), None, fallback_coordinator=c1, fallback_device_tracker="dt", fallback_notifier="n")
    assert fb == [(c1, "dt", "n")]


@pytest.mark.asyncio
async def test_async_register_services_and_service_handlers():
    coord = FakeCoordinator()
    hass = FakeHass(states={"device_tracker.test": FakeState({"latitude": 45.1, "longitude": 9.1})})
    hass.data[DOMAIN]["coordinators"] = {"entry_1": coord}

    await services.async_register_services(hass, coord, "device_tracker.test", "mobile_app")

    save_fn = hass.services._registry[(DOMAIN, "save_position")]
    await save_fn(FakeCall({"require_fresh_position": "false", "notify_waiting": "true"}))
    assert coord.saved_calls[-1] == (45.1, 9.1, False, True, "save")

    mute_fn = hass.services._registry[(DOMAIN, "mute_notifications")]
    unmute_fn = hass.services._registry[(DOMAIN, "unmute_notifications")]
    reset_fn = hass.services._registry[(DOMAIN, "reset_flags")]
    clear_fn = hass.services._registry[(DOMAIN, "clear_persisted")]

    await mute_fn()
    assert coord.position_notified is True
    await unmute_fn()
    assert coord.position_notified is False
    await reset_fn()
    assert coord.position_notified is False

    coord.alarm_active = True
    await clear_fn()
    assert coord.saved_latitude is None
    assert coord.saved_longitude is None
    assert coord.alarm_active is False


@pytest.mark.asyncio
async def test_async_register_services_skips_when_already_registered():
    coord = FakeCoordinator()
    hass = FakeHass()
    hass.services._existing.add((DOMAIN, "save_position"))

    await services.async_register_services(hass, coord, "device_tracker.test", "mobile_app")

    assert (DOMAIN, "save_position") not in hass.services._registry


@pytest.mark.asyncio
async def test_async_register_helper_services_and_handlers():
    coord = FakeCoordinator(entry_id="entry_1")
    hass = FakeHass()
    hass.data[DOMAIN]["coordinators"] = {"entry_1": coord}
    hass.data[DOMAIN]["_webhook_to_entry"] = {"tok-1": "entry_1"}

    await services.async_register_helper_services(hass, coord, "entry_1", "tok-1")

    get_info = hass.services._registry[(DOMAIN, "get_webhook_info")]
    info_specific = await get_info(FakeCall({"config_entry": "entry_1"}))
    assert info_specific["webhook_id"] == "tok-1"

    info_missing = await get_info(FakeCall({"config_entry": "missing"}))
    assert "error" in info_missing

    start_fn = hass.services._registry[(DOMAIN, "start")]
    stop_fn = hass.services._registry[(DOMAIN, "stop")]
    toggle_fn = hass.services._registry[(DOMAIN, "toggle_alarm")]

    await start_fn(FakeCall({"notify_waiting": True}))
    assert coord.set_alarm_calls[-1] == (True, True)

    await stop_fn()
    assert coord.set_alarm_calls[-1] == (False, False)

    coord.alarm_active = False
    await toggle_fn()
    assert coord.set_alarm_calls[-1][0] is True

    dbg = hass.services._registry[(DOMAIN, "debug_multi_instance")]
    dbg_data = await dbg()
    assert "coordinators" in dbg_data


@pytest.mark.asyncio
async def test_helper_services_cleanup_and_list_webhooks():
    coord = FakeCoordinator(entry_id="entry_1")
    hass = FakeHass()
    hass.data[DOMAIN]["coordinators"] = {"entry_1": coord}
    hass.data["webhook"] = SimpleNamespace(_handlers={"abc": object(), "vehicle-save-location": object()})

    await services.async_register_helper_services(hass, coord, "entry_1", "tok-1")

    with patch("custom_components.tag_guard_vehicle.services.async_cleanup_old_webhooks", new_callable=AsyncMock) as cleanup_mock:
        cleanup_fn = hass.services._registry[(DOMAIN, "cleanup_webhooks")]
        await cleanup_fn()
        cleanup_mock.assert_awaited()

    list_fn = hass.services._registry[(DOMAIN, "list_webhooks")]
    out = await list_fn()
    assert "all_webhooks" in out


@pytest.mark.asyncio
async def test_register_webhook_and_listener_and_route_handler():
    coord = FakeCoordinator(entry_id="entry_1")
    coord.config["device_tracker"] = "device_tracker.route"
    hass = FakeHass(states={"device_tracker.route": FakeState({"latitude": 1, "longitude": 2})})
    hass.data[DOMAIN]["coordinators"] = {"entry_1": coord}

    captured = {}

    def fake_register(hass_arg, domain, name, webhook_id, handler):
        captured["handler"] = handler
        captured["webhook_id"] = webhook_id

    with patch("homeassistant.components.webhook.async_register", side_effect=fake_register):
        await services.async_register_webhook_and_listeners(hass, coord, "device_tracker.route", webhook_id="tok-xyz")

    assert hass.data[DOMAIN]["_webhook_to_entry"]["tok-xyz"] == "entry_1"
    assert "_mobile_action_listener" in hass.data[DOMAIN]

    handler = captured["handler"]

    req = SimpleNamespace(method="POST", path="/api/webhook/tok-xyz", headers={}, query={})
    req.json = AsyncMock(return_value={"action": "stop"})

    resp_ok = await handler(hass, "tok-xyz", req)
    assert resp_ok.status == 200

    resp_unknown = await handler(hass, "unknown", req)
    assert resp_unknown.status == 404

    hass.data[DOMAIN]["_webhook_to_entry"]["tok-missing"] = "missing-entry"
    resp_missing = await handler(hass, "tok-missing", req)
    assert resp_missing.status == 404


@pytest.mark.asyncio
async def test_register_webhook_raises_valueerror_and_runtimeerror():
    coord = FakeCoordinator(entry_id="entry_1")
    hass = FakeHass()
    hass.data[DOMAIN]["coordinators"] = {"entry_1": coord}

    with patch("homeassistant.components.webhook.async_register", side_effect=ValueError("dup")):
        with pytest.raises(ValueError):
            await services.async_register_webhook_and_listeners(hass, coord, "device_tracker.test", webhook_id="tok-dup")

    with patch("homeassistant.components.webhook.async_register", side_effect=Exception("boom")):
        with pytest.raises(RuntimeError):
            await services.async_register_webhook_and_listeners(hass, coord, "device_tracker.test", webhook_id="tok-err")


@pytest.mark.asyncio
async def test_async_cleanup_old_webhooks_unregisters_default_and_current_token():
    coord = FakeCoordinator(entry_id="entry_1")
    coord.config["options"]["webhook_token"] = "tok-clean"
    hass = FakeHass()

    calls = []

    def fake_unregister(h, webhook_id):
        calls.append(webhook_id)

    with patch("homeassistant.components.webhook.async_unregister", side_effect=fake_unregister):
        await services.async_cleanup_old_webhooks(hass, coord)

    assert DEFAULT_WEBHOOK_ID in calls
    assert "tok-clean" in calls
