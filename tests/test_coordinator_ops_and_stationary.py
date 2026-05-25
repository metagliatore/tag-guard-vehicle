from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeServices:
	async def async_call(self, domain, service, data):
		return None


class FakeStates:
	def __init__(self, state=None):
		self._state = state

	def get(self, entity_id):
		return self._state


class FakeHass:
	def __init__(self, state=None):
		self.services = FakeServices()
		self.states = FakeStates(state)


class FakeState:
	def __init__(self, attrs):
		self.attributes = attrs


class FakeEvent:
	def __init__(self, old_state, new_state, entity_id="device_tracker.test"):
		self.data = {
			"entity_id": entity_id,
			"old_state": old_state,
			"new_state": new_state,
		}


@pytest.mark.asyncio
async def test_counter_is_capped_for_stationary_count_gt_zero():
	old_state = FakeState({
		"ops": [{"extra": {"gpsUtcDt": "20250101000000"}, "latitude": "45.5", "longitude": "9.2"}],
		"latitude": 45.5,
		"longitude": 9.2,
	})
	new_state = FakeState({
		"ops": [{"extra": {"gpsUtcDt": "20250101000001"}, "latitude": "45.5", "longitude": "9.2"}],
		"latitude": 45.5,
		"longitude": 9.2,
	})
	hass = FakeHass()
	coordinator = VehicleCoordinator(
		hass,
		"entry_1",
		{
			"activation_mode": "position",
			"stationary_count": 2,
			"stationary_minutes": 1,
			"tolerance_radius": 200,
		},
	)
	coordinator.async_save = AsyncMock()
	coordinator._stationary_candidate = (45.5, 9.2)
	coordinator._stationary_counter = 20
	coordinator._last_accepted_gps_timestamp = "20250101000000"

	with patch("custom_components.tag_guard_vehicle.coordinator.async_call_later", return_value=MagicMock()):
		await coordinator._handle_device_event(FakeEvent(old_state, new_state))

	assert coordinator._stationary_counter == 10


@pytest.mark.asyncio
async def test_stationary_count_zero_keeps_counter_zero_and_sets_candidate():
	old_state = FakeState({
		"ops": [{"extra": {"gpsUtcDt": "20250101000000"}, "latitude": "45.5", "longitude": "9.2"}],
		"latitude": 45.5,
		"longitude": 9.2,
	})
	new_state = FakeState({
		"ops": [{"extra": {"gpsUtcDt": "20250101000001"}, "latitude": "45.5", "longitude": "9.2"}],
		"latitude": 45.5,
		"longitude": 9.2,
	})
	hass = FakeHass()
	coordinator = VehicleCoordinator(
		hass,
		"entry_1",
		{
			"activation_mode": "position",
			"stationary_count": 0,
			"stationary_minutes": 1,
			"tolerance_radius": 200,
		},
	)
	coordinator.async_save = AsyncMock()

	with patch("custom_components.tag_guard_vehicle.coordinator.async_call_later", return_value=MagicMock()):
		await coordinator._handle_device_event(FakeEvent(old_state, new_state))

	assert coordinator._stationary_counter == 0
	assert coordinator._stationary_candidate == (45.5, 9.2)

