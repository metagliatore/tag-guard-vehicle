from unittest.mock import AsyncMock

import pytest

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeServices:
	def __init__(self):
		self.calls = []

	async def async_call(self, domain, service, data):
		self.calls.append((domain, service, data))


class FakeStates:
	def get(self, entity_id):
		return None


class FakeHass:
	def __init__(self):
		self.services = FakeServices()
		self.states = FakeStates()


@pytest.mark.asyncio
async def test_async_handle_action_ignores_other_entry_suffix():
	hass = FakeHass()
	coordinator = VehicleCoordinator(hass, "entry_1", {"notifier": "mobile_app"})
	coordinator.saved_latitude = 45.5
	coordinator.saved_longitude = 9.2

	await coordinator.async_handle_action("OPEN_MAP_entry_2")

	assert hass.services.calls == []


@pytest.mark.asyncio
async def test_async_handle_action_open_map_sends_notification():
	hass = FakeHass()
	coordinator = VehicleCoordinator(hass, "ENTRY1", {"notifier": "mobile_app"})
	coordinator.saved_latitude = 45.5
	coordinator.saved_longitude = 9.2

	await coordinator.async_handle_action("OPEN_MAP_ENTRY1")

	assert len(hass.services.calls) == 1
	domain, service, data = hass.services.calls[0]
	assert domain == "notify"
	assert service == "mobile_app"
	assert "https://maps.google.com/?q=45.5,9.2" in data["message"]


@pytest.mark.asyncio
async def test_async_handle_action_disable_alarm_calls_set_alarm_active():
	hass = FakeHass()
	coordinator = VehicleCoordinator(hass, "ENTRY1", {"notifier": "mobile_app"})
	coordinator.set_alarm_active = AsyncMock()

	await coordinator.async_handle_action("DISABLE_ALARM_ENTRY1")

	coordinator.set_alarm_active.assert_awaited_once_with(False)

