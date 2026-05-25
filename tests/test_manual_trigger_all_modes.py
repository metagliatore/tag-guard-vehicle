from unittest.mock import AsyncMock

import pytest

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeServices:
	async def async_call(self, domain, service, data):
		return None


class FakeStates:
	def get(self, entity_id):
		return None


class FakeHass:
	def __init__(self):
		self.services = FakeServices()
		self.states = FakeStates()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["manual", "connection", "position", "combined"])
async def test_set_alarm_active_true_supported_for_all_modes(mode):
	config = {
		"activation_mode": mode,
		"device_tracker": "device_tracker.test",
	}
	coordinator = VehicleCoordinator(FakeHass(), f"entry_{mode}", config)
	coordinator.async_save = AsyncMock()

	await coordinator.set_alarm_active(True)

	assert coordinator.alarm_active is True


@pytest.mark.asyncio
async def test_set_alarm_active_false_disables_alarm():
	coordinator = VehicleCoordinator(FakeHass(), "entry_1", {"activation_mode": "manual"})
	coordinator.async_save = AsyncMock()
	coordinator.alarm_active = True

	await coordinator.set_alarm_active(False)

	assert coordinator.alarm_active is False

