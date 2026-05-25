from unittest.mock import AsyncMock

import pytest

from custom_components.tag_guard_vehicle.const import DOMAIN
from custom_components.tag_guard_vehicle.services import _notify, process_mobile_action


class FakeServices:
	def __init__(self):
		self.calls = []

	async def async_call(self, domain, service, data):
		self.calls.append((domain, service, data))


class FakeHass:
	def __init__(self):
		self.services = FakeServices()
		self.data = {DOMAIN: {"coordinators": {}}}


@pytest.mark.asyncio
async def test_process_mobile_action_forwards_to_all_coordinators():
	hass = FakeHass()
	c1 = type("Coord", (), {"async_handle_action": AsyncMock()})()
	c2 = type("Coord", (), {"async_handle_action": AsyncMock()})()
	hass.data[DOMAIN]["coordinators"] = {"entry_1": c1, "entry_2": c2}

	await process_mobile_action(hass, {"action": "OPEN_MAP"})

	c1.async_handle_action.assert_awaited_once_with("OPEN_MAP", {"action": "OPEN_MAP"})
	c2.async_handle_action.assert_awaited_once_with("OPEN_MAP", {"action": "OPEN_MAP"})


@pytest.mark.asyncio
async def test_notify_calls_notify_service():
	hass = FakeHass()

	await _notify(hass, "mobile_app", "title", "message")

	assert hass.services.calls == [("notify", "mobile_app", {"title": "title", "message": "message"})]

