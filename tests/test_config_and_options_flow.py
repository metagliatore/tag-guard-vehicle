import pytest

from custom_components.tag_guard_vehicle.utils import is_webhook_token_in_use


class FakeEntry:
	def __init__(self, entry_id: str, data=None, options=None):
		self.entry_id = entry_id
		self.data = data or {}
		self.options = options or {}


class FakeConfigEntries:
	def __init__(self, entries):
		self._entries = entries

	def async_entries(self, domain):
		return self._entries


class FakeHass:
	def __init__(self, entries):
		self.config_entries = FakeConfigEntries(entries)


def test_config_flow_webhook_token_in_use_true():
	entry = FakeEntry("entry_1", options={"webhook_token": "token-a"})
	hass = FakeHass([entry])
	assert is_webhook_token_in_use(hass, "token-a") is True


def test_config_flow_webhook_token_in_use_excluding_entry():
	entry = FakeEntry("entry_1", options={"webhook_token": "token-a"})
	hass = FakeHass([entry])
	assert is_webhook_token_in_use(hass, "token-a", exclude_entry_id="entry_1") is False


def test_options_flow_webhook_token_in_use_true():
	entry = FakeEntry("entry_1", data={"webhook_token": "token-b"})
	hass = FakeHass([entry])
	assert is_webhook_token_in_use(hass, "token-b") is True


def test_options_flow_webhook_token_in_use_empty_token():
	hass = FakeHass([])
	assert is_webhook_token_in_use(hass, "") is False

"""Focused tests for config/options flow helpers and branching."""

from types import SimpleNamespace

import pytest

from custom_components.tag_guard_vehicle.options_flow import (
	TagGuardVehicleOptionsFlowHandler,
)
from custom_components.tag_guard_vehicle.utils import is_webhook_token_in_use


def _fake_entry(entry_id: str, data_token: str | None = None, options_token: str | None = None):
	return SimpleNamespace(
		entry_id=entry_id,
		data={"webhook_token": data_token} if data_token else {},
		options={"webhook_token": options_token} if options_token else {},
	)


def test_config_flow_token_uniqueness_detects_collision():
	entries = [
		_fake_entry("a", options_token="token-a"),
		_fake_entry("b", data_token="token-b"),
	]
	hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _domain: entries))

	assert is_webhook_token_in_use(hass, "token-a") is True
	assert is_webhook_token_in_use(hass, "token-b") is True
	assert is_webhook_token_in_use(hass, "new-token") is False


def test_options_flow_token_uniqueness_excludes_current_entry():
	entries = [
		_fake_entry("same", options_token="token-same"),
		_fake_entry("other", options_token="token-other"),
	]
	hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _domain: entries))

	assert is_webhook_token_in_use(hass, "token-same", exclude_entry_id="same") is False
	assert is_webhook_token_in_use(hass, "token-other", exclude_entry_id="same") is True


@pytest.mark.asyncio
async def test_options_flow_branches_to_stationary_for_position_mode():
	entry = _fake_entry("entry-1")
	flow = TagGuardVehicleOptionsFlowHandler(entry)

	result = await flow.async_step_init(
		{
			"person_entity": "person.me",
			"notifier": "notify.me",
			"tolerance_radius": 200,
			"activation_mode": "position",
			"debug_mode": False,
		}
	)

	assert result["type"] == "form"
	assert result["step_id"] == "stationary"


def test_config_flow_async_get_options_flow():
	from custom_components.tag_guard_vehicle.config_flow import TagGuardVehicleConfigFlow
	entry = _fake_entry("entry-1")
	flow = TagGuardVehicleConfigFlow.async_get_options_flow(entry)
	assert isinstance(flow, TagGuardVehicleOptionsFlowHandler)
	assert flow.config_entry == entry


@pytest.mark.asyncio
async def test_options_flow_init_form_shows_all_parameters():
	from custom_components.tag_guard_vehicle.const import CONF_DEVICE_TRACKER, CONF_NOTIFIER, CONF_TOLERANCE_RADIUS, CONF_ACTIVATION_MODE

	entry = SimpleNamespace(
		entry_id="test_entry",
		data={CONF_DEVICE_TRACKER: "device_tracker.my_car"},
		options={
			CONF_NOTIFIER: "notify.mobile_app",
			CONF_TOLERANCE_RADIUS: 150,
			CONF_ACTIVATION_MODE: "combined",
			"webhook_token": "secret_token_123",
			"debug_mode": True,
		},
	)
	hass = SimpleNamespace(
		config=SimpleNamespace(api=SimpleNamespace(base_url="https://ha.example.com")),
		services=SimpleNamespace(async_services=lambda: {"notify": {"mobile_app": {}}}),
	)
	flow = TagGuardVehicleOptionsFlowHandler(entry)
	flow.hass = hass

	result = await flow.async_step_init(None)
	assert result["type"] == "form"
	assert result["step_id"] == "init"
	assert "webhook_url" in result["description_placeholders"]
	assert "https://ha.example.com/api/webhook/secret_token_123" == result["description_placeholders"]["webhook_url"]
	assert result["description_placeholders"]["webhook_token"] == "secret_token_123"


@pytest.mark.asyncio
async def test_options_flow_updates_device_tracker_in_entry_data():
	from custom_components.tag_guard_vehicle.const import CONF_DEVICE_TRACKER

	entry = SimpleNamespace(
		entry_id="test_entry",
		data={CONF_DEVICE_TRACKER: "device_tracker.old_car"},
		options={"activation_mode": "manual"},
	)
	updated_data = {}
	fake_config_entries = SimpleNamespace(
		async_update_entry=lambda e, data=None: updated_data.update(data or {})
	)
	hass = SimpleNamespace(
		config_entries=fake_config_entries,
		services=SimpleNamespace(async_services=lambda: {}),
	)
	flow = TagGuardVehicleOptionsFlowHandler(entry)
	flow.hass = hass

	result = await flow.async_step_init({
		CONF_DEVICE_TRACKER: "device_tracker.new_car",
		"activation_mode": "manual",
	})
	assert result["type"] == "create_entry"
	assert updated_data.get(CONF_DEVICE_TRACKER) == "device_tracker.new_car"


def test_get_webhook_url_variations():
	from custom_components.tag_guard_vehicle.utils import get_webhook_url

	# Empty token
	assert get_webhook_url(None, "") == ""
	assert get_webhook_url(None, None) == ""

	# No hass provided
	assert get_webhook_url(None, "my_token") == "my_token"

	# Hass with api.base_url
	hass_base = SimpleNamespace(config=SimpleNamespace(api=SimpleNamespace(base_url="http://my-ha:8123/")))
	assert get_webhook_url(hass_base, "tok123") == "http://my-ha:8123/api/webhook/tok123"

	# Hass with external_url fallback
	hass_ext = SimpleNamespace(config=SimpleNamespace(external_url="https://remote.ha.com", internal_url=None))
	assert get_webhook_url(hass_ext, "tok456") == "https://remote.ha.com/api/webhook/tok456"


