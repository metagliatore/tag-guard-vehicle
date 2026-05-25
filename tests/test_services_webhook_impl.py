from unittest.mock import AsyncMock

import pytest

from custom_components.tag_guard_vehicle.services import handle_webhook_impl


class FakeRequest:
	def __init__(self, method="POST", payload=None, path="/api/webhook/token"):
		self.method = method
		self._payload = payload or {}
		self.path = path
		self.headers = {}
		self.query = {}

	async def json(self):
		return self._payload


class FakeHass:
	pass


class FakeCoordinator:
	def __init__(self):
		self.entry_id = "entry_1"
		self.config = {"device_tracker": "device_tracker.test", "options": {}}
		self.alarm_active = False
		self.position_notified = False
		self.set_alarm_active = AsyncMock()
		self.async_save = AsyncMock()


@pytest.mark.asyncio
async def test_handle_webhook_impl_get_returns_html_page():
	resp = await handle_webhook_impl(FakeHass(), FakeCoordinator(), "device_tracker.test", FakeRequest(method="GET"))

	assert resp.status == 200
	assert resp.content_type == "text/html"


@pytest.mark.asyncio
async def test_handle_webhook_impl_without_action_returns_400():
	resp = await handle_webhook_impl(FakeHass(), FakeCoordinator(), "device_tracker.test", FakeRequest(payload={}))

	assert resp.status == 400


@pytest.mark.asyncio
async def test_handle_webhook_impl_start_action_parses_notify_waiting_string_bool():
	coordinator = FakeCoordinator()
	req = FakeRequest(payload={"action": "start", "notify_waiting": "true"})

	resp = await handle_webhook_impl(FakeHass(), coordinator, "device_tracker.test", req)

	assert resp.status == 200
	coordinator.set_alarm_active.assert_awaited_once_with(True, notify_waiting=True)

