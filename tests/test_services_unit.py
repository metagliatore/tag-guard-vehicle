"""Unit tests for service handlers (save_position, manual_trigger, reset_flags).
"""

import asyncio
from aiohttp import web

import sys
from pathlib import Path

# make repository root importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.vehicle_bt_parking_sentinel import services


class FakeState:
    def __init__(self, lat=None, lon=None):
        self.attributes = {}
        if lat is not None:
            self.attributes["latitude"] = lat
        if lon is not None:
            self.attributes["longitude"] = lon


class FakeHass:
    def __init__(self, states_map=None):
        self.states_map = states_map or {}
        self.services = self
        # provide minimal interface: states.get
        class S:
            def __init__(self, m):
                self.m = m

            def get(self, k):
                return self.m.get(k)

        self.states = S(self.states_map)


class FakeCoordinator:
    def __init__(self, token=None):
        self.config = {"options": {"webhook_token": token}} if token is not None else {"options": {}}
        self.saved = None

    async def _async_save_position(self, lat, lon, gpsUtcDt=None, locationType=None, last_seen=None, reason="save"):
        self.saved = (lat, lon)


class FakeRequest:
    def __init__(self, payload=None, headers=None, query=None):
        self._payload = payload or {}
        self.headers = headers or {}
        self.query = query or {}

    async def json(self):
        return self._payload


# Test: validate_and_extract_coords returns unauthorized when the provided token mismatches
# NOTE: Token validation removed - token is now in the webhook URL path, not validated per-request
# def test_validate_and_extract_coords_token_required_and_wrong():
#     coord = FakeCoordinator(token="secret")
#     hass = FakeHass()
#     ok, status, lat, lon, http_status = services.validate_and_extract_coords(coord, hass, "device_tracker.foo", {})
#     assert not ok
#     assert status == "unauthorized"
#     assert http_status == 401


# Test: validate_and_extract_coords uses device_tracker state attributes
def test_validate_and_extract_coords_fallback_to_tracker():
    coord = FakeCoordinator(token=None)
    state = FakeState(lat="12.34", lon="56.78")
    hass = FakeHass(states_map={"device_tracker.foo": state})
    ok, status, lat, lon, http_status = services.validate_and_extract_coords(coord, hass, "device_tracker.foo", {})
    assert ok and status == "ok"
    assert lat == "12.34" and lon == "56.78"


# Test: handle_webhook_impl accepts payload coordinates and saves them to the coordinator
def test_handle_webhook_impl_saves_coords():
    coord = FakeCoordinator()
    state = FakeState(lat="1", lon="2")
    hass = FakeHass(states_map={"device_tracker.foo": state})

    # According to current webhook semantics, save action must be explicit
    # and payload coordinates are ignored for webhook saves. The handler
    # will read coordinates from the device_tracker state instead.
    req = FakeRequest(payload={"action": "save"}, headers={})

    resp = asyncio.run(services.handle_webhook_impl(hass, coord, "device_tracker.foo", req))
    assert isinstance(resp, web.Response)
    assert resp.status == 200
    # saved coords come from the device_tracker FakeState (strings converted to float)
    assert coord.saved == (1.0, 2.0)


# Test: handle_webhook_impl returns 400 when there are no coordinates available anywhere
def test_handle_webhook_impl_missing_coords_and_fallback():
    coord = FakeCoordinator()
    hass = FakeHass(states_map={})
    req = FakeRequest(payload={}, headers={})
    resp = asyncio.run(services.handle_webhook_impl(hass, coord, "device_tracker.foo", req))
    assert isinstance(resp, web.Response)
    assert resp.status == 400
