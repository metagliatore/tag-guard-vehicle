from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data):
        self.calls.append((domain, service, data))


class FakeStates:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def get(self, entity_id):
        return self.mapping.get(entity_id)


class FakeHass:
    def __init__(self, states_map=None):
        self.states = FakeStates(states_map)
        self.services = FakeServices()
        self.created_tasks = []

    def async_create_task(self, coro):
        self.created_tasks.append(coro)


class FakeEvent:
    def __init__(self, old_state=None, new_state=None, entity_id="device_tracker.test"):
        self.data = {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
        }


@pytest.mark.asyncio
async def test_async_update_options_applies_valid_and_ignores_invalid_numbers():
    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {"tag_model": "samsung_smarttag2"})

    old_tol = c.tolerance_radius
    old_min = c.stationary_minutes
    old_count = c.stationary_count

    await c.async_update_options(
        {
            "notifier": "mobile_app",
            "person_entity": "person.test",
            "activation_mode": "position",
            "tolerance_radius": "bad",
            "stationary_minutes": "bad",
            "stationary_count": "bad",
            "debug_mode": True,
            "tag_model": "samsung_smarttag2",
        }
    )

    assert c.notifier == "mobile_app"
    assert c.person_entity == "person.test"
    assert c.activation_mode == "position"
    assert c.debug_mode is True
    assert c.tolerance_radius == old_tol
    assert c.stationary_minutes == old_min
    assert c.stationary_count == old_count


@pytest.mark.asyncio
async def test_async_start_and_stop_cleanup_handles():
    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {})

    unsub_track = MagicMock()
    timer_cancel = MagicMock()

    with patch("custom_components.tag_guard_vehicle.coordinator.async_track_state_change_event", return_value=unsub_track):
        await c.async_start("device_tracker.test")

    c._stationary_handle = timer_cancel
    await c.async_stop()

    unsub_track.assert_called_once()
    timer_cancel.assert_called_once()
    assert c._unsub_track is None
    assert c._stationary_handle is None


@pytest.mark.asyncio
async def test_async_device_tracker_changed_schedules_task():
    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {})

    c._async_device_tracker_changed(FakeEvent())

    assert len(hass.created_tasks) == 1
    for coro in hass.created_tasks:
        coro.close()


@pytest.mark.asyncio
async def test_handle_device_event_returns_early_when_new_state_none():
    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {})
    c.async_save = AsyncMock()

    await c._handle_device_event(FakeEvent(old_state=None, new_state=None))

    c.async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_device_event_skips_when_same_gps_and_candidate_exists():
    old_state = SimpleNamespace(attributes={"ops": [{"extra": {"gpsUtcDt": "20250101000000"}}]})
    new_state = SimpleNamespace(attributes={"ops": [{"extra": {"gpsUtcDt": "20250101000000"}}]})

    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {"activation_mode": "position"})
    c.async_save = AsyncMock()
    c._stationary_candidate = (45.5, 9.2)

    await c._handle_device_event(FakeEvent(old_state=old_state, new_state=new_state))

    c.async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_returns_without_device_tracker():
    hass = FakeHass()
    c = VehicleCoordinator(hass, "entry_1", {})
    c._async_save_position = AsyncMock()

    await c._stationary_check(45.5, 9.2)

    c._async_save_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_returns_when_state_missing_or_coords_missing():
    c1 = VehicleCoordinator(FakeHass({}), "entry_1", {"device_tracker": "device_tracker.test"})
    c1._async_save_position = AsyncMock()
    await c1._stationary_check(45.5, 9.2)
    c1._async_save_position.assert_not_awaited()

    no_coords_state = SimpleNamespace(attributes={})
    c2 = VehicleCoordinator(FakeHass({"device_tracker.test": no_coords_state}), "entry_2", {"device_tracker": "device_tracker.test"})
    c2._async_save_position = AsyncMock()
    await c2._stationary_check(45.5, 9.2)
    c2._async_save_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_does_not_save_when_distance_exceeds_tolerance():
    state = SimpleNamespace(attributes={"latitude": 46.0, "longitude": 10.0})
    c = VehicleCoordinator(FakeHass({"device_tracker.test": state}), "entry_1", {"device_tracker": "device_tracker.test", "tolerance_radius": 50})
    c._async_save_position = AsyncMock()

    await c._stationary_check(45.5, 9.2)

    c._async_save_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_counter_below_threshold_skips_save():
    state = SimpleNamespace(attributes={"latitude": 45.5, "longitude": 9.2})
    c = VehicleCoordinator(
        FakeHass({"device_tracker.test": state}),
        "entry_1",
        {"device_tracker": "device_tracker.test", "activation_mode": "position", "stationary_count": 3, "tolerance_radius": 200},
    )
    c._stationary_counter = 1
    c._async_save_position = AsyncMock()

    await c._stationary_check(45.5, 9.2)

    c._async_save_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_timestamp_gate_skips_when_not_fresh_for_count_gt_zero():
    attrs = {
        "latitude": 45.5,
        "longitude": 9.2,
        "ops": [{"extra": {"gpsUtcDt": "20250101000000"}}],
    }
    state = SimpleNamespace(attributes=attrs)
    c = VehicleCoordinator(
        FakeHass({"device_tracker.test": state}),
        "entry_1",
        {"device_tracker": "device_tracker.test", "activation_mode": "position", "stationary_count": 1, "tolerance_radius": 200},
    )
    c._stationary_counter = 1
    c._stationary_candidate_gpsUtcDt = "20250101000000"
    c._stationary_start_utc = "20250101000001"
    c._async_save_position = AsyncMock()

    await c._stationary_check(45.5, 9.2)

    c._async_save_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_stationary_check_saves_for_stationary_count_zero():
    attrs = {
        "latitude": 45.5,
        "longitude": 9.2,
        "ops": [{"extra": {"gpsUtcDt": "20250101000000", "locationType": "basic"}}],
        "last_seen": "2025-01-01T00:00:00+00:00",
    }
    state = SimpleNamespace(attributes=attrs)
    c = VehicleCoordinator(
        FakeHass({"device_tracker.test": state}),
        "entry_1",
        {"device_tracker": "device_tracker.test", "activation_mode": "position", "stationary_count": 0, "tolerance_radius": 200},
    )
    c._stationary_counter = 0
    c._async_save_position = AsyncMock()

    await c._stationary_check(45.5, 9.2)

    c._async_save_position.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_movement_no_notifier_returns_early():
    c = VehicleCoordinator(FakeHass(), "entry_1", {})
    c.notifier = None

    await c._notify_movement(45.6, 9.3)

    assert c.hass.services.calls == []
