"""Coordinator behaviour tests using fake dependencies.

These validate coordinator logic in a controlled, fake environment.
"""

import asyncio
import pytest

from custom_components.vehicle_bt_parking_sentinel.coordinator import VehicleCoordinator
from custom_components.vehicle_bt_parking_sentinel.utils import haversine_distance


class DummyStore:
    def __init__(self):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


class FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data=None):
        self.calls.append((domain, service, data))


class FakeBus:
    def __init__(self):
        self.listeners = []

    def async_listen(self, event_type, cb):
        self.listeners.append((event_type, cb))


class FakeStates:
    def __init__(self):
        self._dict = {}

    def get(self, entity_id):
        return self._dict.get(entity_id)


class FakeHass:
    def __init__(self):
        self.services = FakeServices()
        self.bus = FakeBus()
        self.states = FakeStates()
        self._tasks = []

    def async_create_task(self, coro):
        # schedule on loop
        t = asyncio.get_event_loop().create_task(coro)
        self._tasks.append(t)
        return t


class DummyEvent:
    def __init__(self, entity_id, new_state, old_state=None):
        self.data = {"entity_id": entity_id, "new_state": new_state, "old_state": old_state}


class FakeState:
    def __init__(self, attrs):
        self.attributes = attrs


@pytest.mark.asyncio
@pytest.mark.asyncio
# Integration-style test: a disconnect event with coords causes a save
async def test_disconnect_saves_position(monkeypatch):
    hass = FakeHass()
    coord = VehicleCoordinator(hass, "e1", {})
    coord.store = DummyStore()
    coord.notifier = None
    # patch async_call_later to a no-op to avoid scheduling
    monkeypatch.setattr("custom_components.vehicle_bt_parking_sentinel.coordinator.async_call_later", lambda *a, **k: (lambda: None))

    # simulate a disconnect event with coords (op that yields disconnected)
    new_state = FakeState({"ops": [{"oprnType": "OTHER", "oprnResultCode": "0000", "oprnStsCd": "0000", "extra": {"latitude": 45.0, "longitude": 9.0}}]})
    ev = DummyEvent("device.tracker_1", new_state)
    # call handler
    await coord._handle_device_event(ev)
    # saved position should be set
    assert coord.saved_latitude == 45.0
    assert coord.saved_longitude == 9.0


@pytest.mark.asyncio
@pytest.mark.asyncio
# When alarm is active and movement occurs, a notification is sent
async def test_movement_triggers_notify(monkeypatch):
    hass = FakeHass()
    coord = VehicleCoordinator(hass, "e2", {})
    coord.store = DummyStore()
    coord.notifier = "notify.test"
    # set saved position and ensure last_tag_state indicates no recent change
    coord.saved_latitude = 45.0
    coord.saved_longitude = 9.0
    coord.last_tag_state = "disconnected"
    coord.alarm_active = True
    # patch _notify_movement to record calls instead of real notify
    called = {}

    async def fake_notify(lat, lon):
        called['lat'] = lat
        called['lon'] = lon

    monkeypatch.setattr(coord, "_notify_movement", fake_notify)

    # patch async_call_later to avoid scheduling
    monkeypatch.setattr("custom_components.vehicle_bt_parking_sentinel.coordinator.async_call_later", lambda *a, **k: (lambda: None))

    new_state = FakeState({"latitude": 45.01, "longitude": 9.0})
    ev = DummyEvent("device.tracker_1", new_state)
    await coord._handle_device_event(ev)
    # _notify_movement should have been called with the coordinates
    assert 'lat' in called
    assert 'lon' in called
    assert called['lat'] == 45.01
    assert called['lon'] == 9.0


@pytest.mark.asyncio
@pytest.mark.asyncio
# Combined mode requires stationary criteria before a disconnect triggers save
async def test_combined_requires_stationary_then_disconnect(monkeypatch):
    hass = FakeHass()
    coord = VehicleCoordinator(hass, "e3", {})
    coord.store = DummyStore()
    coord.notifier = None
    coord.activation_mode = "combined"
    coord.stationary_count = 2
    # patch async_call_later to call the callback immediately
    def fake_call_later(hass_arg, seconds, callback):
        # simulate immediate timer firing by invoking the callback directly
        callback(None)
        return lambda: None

    monkeypatch.setattr("custom_components.vehicle_bt_parking_sentinel.coordinator.async_call_later", fake_call_later)

    # ensure device tracker configured so stationary_check can read current state
    coord.config["device_tracker"] = "device.tracker_1"
    hass.states._dict["device.tracker_1"] = FakeState({"latitude": 45.0, "longitude": 9.0})

    # simulate two close reports
    s1 = FakeState({"latitude": 45.0, "longitude": 9.0})
    ev1 = DummyEvent("device.tracker_1", s1)
    await coord._handle_device_event(ev1)
    s2 = FakeState({"latitude": 45.00001, "longitude": 9.0})
    ev2 = DummyEvent("device.tracker_1", s2)
    await coord._handle_device_event(ev2)

    # now simulate disconnect event; include coords
    dis = FakeState({"ops": [{"oprnType": "CHECK_CONNECTION", "oprnResultCode": "1200", "oprnStsCd": "2800", "extra": {"latitude": 45.0, "longitude": 9.0}}]})
    evd = DummyEvent("device.tracker_1", dis)
    await coord._handle_device_event(evd)
    await asyncio.sleep(0.05)
    # saved position should be set after combined criteria (persisted in store)
    assert coord.store._data["saved_latitude"] == 45.0
    assert coord.store._data["saved_longitude"] == 9.0
