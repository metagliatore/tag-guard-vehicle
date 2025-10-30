"""More basic tests: options flow factory, webhook GET, and manual_trigger fallback."""

import asyncio

from aiohttp import web


def test_async_get_options_flow_returns_handler():
    from custom_components.vehicle_bt_parking_sentinel import async_get_options_flow

    class FakeEntry:
        pass

    # Should return an options flow handler class instance (awaitable)
    res = asyncio.run(async_get_options_flow(FakeEntry()))
    # Ensure returned object has the expected handler class name
    assert res.__class__.__name__.endswith("OptionsFlowHandler") or res.__class__.__name__.endswith("VehicleBtParkingSentinelOptionsFlowHandler")


def test_handle_webhook_impl_get_returns_html():
    from custom_components.vehicle_bt_parking_sentinel.services import handle_webhook_impl

    class FakeRequest:
        def __init__(self):
            self.method = "GET"

    class FakeCoordinator:
        pass

    class FakeHass:
        def __init__(self):
            self.data = {}

    hass = FakeHass()
    coord = FakeCoordinator()
    req = FakeRequest()
    resp = asyncio.run(handle_webhook_impl(hass, coord, "device_tracker.foo", req))
    assert isinstance(resp, web.Response)
    assert resp.content_type == "text/html"
    text = resp.text
    assert "button" in text and "start" in text.lower()


def test_start_reads_from_tracker():
    """Test that start service reads from device_tracker and enables alarm."""
    from custom_components.vehicle_bt_parking_sentinel.services import async_register_helper_services
    from datetime import datetime

    class FakeHass:
        def __init__(self, states_map=None):
            self.services = self
            self._states = states_map or {}

        class S:
            def __init__(self, m):
                self.m = m

            def get(self, k):
                return self.m.get(k)

        @property
        def states(self):
            return FakeHass.S(self._states)

        def async_register(self, domain, name, func):
            # Store all registered services in a dict
            if not hasattr(self, '_registered_services'):
                self._registered_services = {}
            self._registered_services[(domain, name)] = func
            # Keep backward compat
            self._registered = func

        async def async_call(self, domain, service, data):
            # no-op for notify calls in tests
            self._last_call = (domain, service, data)
            return None

    class DummyCoordinator:
        def __init__(self, hass, config):
            self.hass = hass
            self.config = config
            self.saved_latitude = None
            self.saved_longitude = None
            self.alarm_active = False
            self._awaiting_activation_save = False
            self._activation_time_str = None

        async def set_alarm_active(self, v: bool, activation_time=None, notify_waiting=False):
            """Simplified set_alarm_active that reads device_tracker and saves if GPS is fresh."""
            self.alarm_active = bool(v)
            await self.async_save()
            
            if self.alarm_active:
                act_ts = activation_time or datetime.utcnow().strftime('%Y%m%d%H%M%S')
                device_entity = self.config.get("device_tracker")
                if device_entity:
                    state = self.hass.states.get(device_entity)
                    if state:
                        lat = state.attributes.get("latitude")
                        lon = state.attributes.get("longitude")
                        # For simplicity in test, just save directly (assume GPS is fresh)
                        if lat and lon:
                            await self._async_save_position(lat, lon)

        async def async_save(self):
            return None

        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = float(lat)
            self.saved_longitude = float(lon)

    # prepare hass with device_tracker state
    class FakeState:
        def __init__(self, lat, lon):
            # Use a future timestamp to ensure GPS is considered fresh
            future_dt = (datetime.utcnow().year + 1) * 10000000000 + 1027232054
            self.attributes = {
                "latitude": lat, 
                "longitude": lon, 
                "ops": [{"extra": {"gpsUtcDt": str(future_dt)}}],
                "gpsUtcDt": str(future_dt)
            }

    state = FakeState("7.7", "8.8")
    hass = FakeHass(states_map={"device.tracker_x": state})
    coord = DummyCoordinator(hass, {"device_tracker": "device.tracker_x", "tag_model": "SmartTag"})

    # register helper services (includes start)
    asyncio.run(async_register_helper_services(hass, coord, "entry_test", "token123"))

    # Get start function
    func = hass._registered_services.get(("vehicle_bt_parking_sentinel", "start"))
    
    # create a dummy call object with .data attribute
    class Call:
        def __init__(self, data=None):
            self.data = data or {}

    # Call start (equivalent to old manual_trigger)
    asyncio.run(func(Call()))
    
    # start service should have:
    # 1. Saved the position from device_tracker
    assert coord.saved_latitude == 7.7
    assert coord.saved_longitude == 8.8
    # 2. Enabled alarm
    assert coord.alarm_active is True
