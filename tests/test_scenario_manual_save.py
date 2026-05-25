from unittest.mock import AsyncMock

import pytest

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeState:
	def __init__(self, attrs):
		self.attributes = attrs


class FakeStates:
	def __init__(self, state):
		self._state = state

	def get(self, entity_id):
		return self._state


class FakeServices:
	async def async_call(self, domain, service, data):
		return None


class FakeHass:
	def __init__(self, state):
		self.states = FakeStates(state)
		self.services = FakeServices()


@pytest.mark.asyncio
async def test_manual_save_without_freshness_saves_immediately():
	state = FakeState({"ops": [{"extra": {"gpsUtcDt": "20000101000000"}}], "gpsUtcDt": "20000101000000"})
	coordinator = VehicleCoordinator(
		FakeHass(state),
		"entry_1",
		{"device_tracker": "device_tracker.test"},
	)
	coordinator._async_save_position = AsyncMock()

	await coordinator._async_save_position_with_freshness_check(45.5, 9.2, require_fresh_position=False)

	coordinator._async_save_position.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_save_with_stale_position_sets_awaiting_state():
	state = FakeState({"ops": [{"extra": {"gpsUtcDt": "20000101000000"}}], "gpsUtcDt": "20000101000000"})
	coordinator = VehicleCoordinator(
		FakeHass(state),
		"entry_1",
		{"device_tracker": "device_tracker.test", "notifier": "mobile_app"},
	)
	coordinator._async_save_position = AsyncMock()

	await coordinator._async_save_position_with_freshness_check(
		45.5,
		9.2,
		require_fresh_position=True,
		notify_waiting=False,
	)

	coordinator._async_save_position.assert_not_awaited()
	assert coordinator._awaiting_activation_save is True
	assert coordinator._activation_time_str is not None

