"""Additional basic tests: integration setup, webhook semantics, and sensor name updates."""

import asyncio

from aiohttp import web


def test_async_setup_creates_domain_dict():
    # minimal fake hass supporting .data
    class H:
        def __init__(self):
            self.data = {}

    from custom_components.vehicle_bt_parking_sentinel import async_setup

    hass = H()
    res = asyncio.run(async_setup(hass, {}))
    assert res is True
    # domain should be present
    assert "vehicle_bt_parking_sentinel" in hass.data


def test_validate_and_extract_coords_ignores_payload_when_disallowed():
    from custom_components.vehicle_bt_parking_sentinel.services import validate_and_extract_coords

    class FakeCoordinator:
        def __init__(self):
            self.config = {"options": {}}

    class FakeState:
        def __init__(self, lat, lon):
            self.attributes = {"latitude": lat, "longitude": lon}

    class FakeHass:
        def __init__(self, states_map):
            self._map = states_map

        class S:
            def __init__(self, m):
                self._m = m

            def get(self, k):
                return self._m.get(k)

        @property
        def states(self):
            return FakeHass.S(self._map)

    coord = FakeCoordinator()
    state = FakeState("12.34", "56.78")
    hass = FakeHass({"device_tracker.foo": state})

    # payload coords different from tracker; allow_payload_coords=False should prefer tracker
    ok, status, lat, lon, http_status = validate_and_extract_coords(coord, hass, "device_tracker.foo", {"latitude": 99, "longitude": 88}, allow_payload_coords=False)
    assert ok is True
    assert lat == "12.34" and lon == "56.78"


def test_handle_webhook_actions_start_and_stop():
    from custom_components.vehicle_bt_parking_sentinel.services import handle_webhook_impl

    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = False

        async def set_alarm_active(self, v: bool):
            self.alarm_active = bool(v)

    class FakeHass:
        def __init__(self):
            self.data = {}

    class FakeRequest:
        def __init__(self, payload=None, headers=None, query=None):
            self._payload = payload or {}
            self.headers = headers or {}
            self.query = query or {}

        async def json(self):
            return self._payload

    coord = FakeCoordinator()
    hass = FakeHass()

    # start action
    req_start = FakeRequest(payload={"action": "start"})
    resp = asyncio.run(handle_webhook_impl(hass, coord, "device_tracker.foo", req_start))
    assert isinstance(resp, web.Response)
    assert resp.status == 200
    assert coord.alarm_active is True

    # disarm action
    req_disarm = FakeRequest(payload={"action": "disarm"})
    resp2 = asyncio.run(handle_webhook_impl(hass, coord, "device_tracker.foo", req_disarm))
    assert isinstance(resp2, web.Response)
    assert resp2.status == 200
    assert coord.alarm_active is False


def test_sensor_entry_updated_changes_name():
    from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor

    class FakeEntry:
        def __init__(self, data=None, options=None, entry_id="testid"):
            self.data = data or {}
            self.options = options or {}
            self.entry_id = entry_id

        def add_update_listener(self, cb):
            # no-op for tests
            pass

    class FakeHass:
        def __init__(self):
            self.data = {}

    hass = FakeHass()
    entry = FakeEntry()
    sensor = VehicleBtParkingSentinelSensor(hass, entry)
    # default name
    assert "Vehicle BT Parking Sentinel" in sensor.name

    # simulate entry updated with new options containing device_tracker
    new_entry = FakeEntry(data={}, options={"device_tracker": "device.tracker_x"})
    asyncio.run(sensor._async_entry_updated(hass, new_entry))
    assert "device.tracker_x" in sensor.name
"""Additional small, focused tests to improve coverage on key runtime paths.

Tests added:
- async_setup creates hass.data[DOMAIN]
- validate_and_extract_coords ignores payload coords when disallowed
- handle_webhook_impl handles start/stop actions
- sensor updates its display name when entry options change
"""

import asyncio

from custom_components.vehicle_bt_parking_sentinel import async_setup
from custom_components.vehicle_bt_parking_sentinel.const import DOMAIN
from custom_components.vehicle_bt_parking_sentinel import services


def test_async_setup_creates_domain_data():
    class FakeHass:
        pass

    hass = FakeHass()
    hass.data = {}
    res = asyncio.run(async_setup(hass, {}))
    assert res is True
    assert DOMAIN in hass.data


def test_validate_and_extract_coords_ignores_payload_when_disabled():
    class FakeCoordinator:
        def __init__(self):
            self.config = {"options": {}}

    class FakeState:
        def __init__(self, lat=None, lon=None):
            self.attributes = {}
            if lat is not None:
                self.attributes["latitude"] = lat
            if lon is not None:
                self.attributes["longitude"] = lon

    class FakeHass:
        def __init__(self, states_map=None):
            self._states = states_map or {}

        class S:
            def __init__(self, m):
                self.m = m

            def get(self, k):
                return self.m.get(k)

        @property
        def states(self):
            return self.S(self._states)

    coord = FakeCoordinator()
    state = FakeState(lat="12.34", lon="56.78")
    hass = FakeHass(states_map={"device_tracker.foo": state})

    ok, status, lat, lon, http_status = services.validate_and_extract_coords(
        coord, hass, "device_tracker.foo", {"latitude": 100.0, "longitude": 200.0}, allow_payload_coords=False
    )
    assert ok and status == "ok"
    # coords must come from the device_tracker state, not from payload
    assert lat == "12.34" and lon == "56.78"


def test_handle_webhook_impl_start_stop_actions():
    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = None

        async def set_alarm_active(self, active: bool):
            self.alarm_active = bool(active)

    class FakeRequest:
        def __init__(self, payload=None, headers=None, query=None):
            self._payload = payload or {}
            self.headers = headers or {}
            self.query = query or {}

        async def json(self):
            return self._payload

    hass = type("H", (), {"data": {}})()
    coord = FakeCoordinator()

    # start
    req_start = FakeRequest(payload={"action": "start"})
    resp = asyncio.run(services.handle_webhook_impl(hass, coord, "device_tracker.foo", req_start))
    assert resp.status == 200
    assert coord.alarm_active is True

    # disarm
    req_disarm = FakeRequest(payload={"action": "disarm"})
    resp2 = asyncio.run(services.handle_webhook_impl(hass, coord, "device_tracker.foo", req_disarm))
    assert resp2.status == 200
    assert coord.alarm_active is False


def test_sensor_name_updates_on_entry_update():
    from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor

    class FakeHass:
        def __init__(self):
            self.data = {}

    class StubEntry:
        def __init__(self, entry_id, data=None, options=None):
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}

    hass = FakeHass()
    entry = StubEntry("e1")
    sensor = VehicleBtParkingSentinelSensor(hass, entry)

    # simulate an updated entry with options containing device_tracker
    updated_entry = StubEntry("e1", data={}, options={"device_tracker": "device.tracker_42"})
    asyncio.run(sensor._async_entry_updated(hass, updated_entry))
    assert "device.tracker_42" in sensor.name
