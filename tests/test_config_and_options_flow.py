import pytest

from custom_components.tag_guard_vehicle.config_flow import is_webhook_token_in_use as cfg_token_in_use
from custom_components.tag_guard_vehicle.options_flow import is_webhook_token_in_use as opt_token_in_use


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
	assert cfg_token_in_use(hass, "token-a") is True


def test_config_flow_webhook_token_in_use_excluding_entry():
	entry = FakeEntry("entry_1", options={"webhook_token": "token-a"})
	hass = FakeHass([entry])
	assert cfg_token_in_use(hass, "token-a", exclude_entry_id="entry_1") is False


def test_options_flow_webhook_token_in_use_true():
	entry = FakeEntry("entry_1", data={"webhook_token": "token-b"})
	hass = FakeHass([entry])
	assert opt_token_in_use(hass, "token-b") is True


def test_options_flow_webhook_token_in_use_empty_token():
	hass = FakeHass([])
	assert opt_token_in_use(hass, "") is False

"""Focused tests for config/options flow helpers and branching."""

from types import SimpleNamespace

import pytest

from custom_components.tag_guard_vehicle.config_flow import is_webhook_token_in_use as cfg_token_in_use
from custom_components.tag_guard_vehicle.options_flow import (
	TagGuardVehicleOptionsFlowHandler,
	is_webhook_token_in_use as opt_token_in_use,
)


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

	assert cfg_token_in_use(hass, "token-a") is True
	assert cfg_token_in_use(hass, "token-b") is True
	assert cfg_token_in_use(hass, "new-token") is False


def test_options_flow_token_uniqueness_excludes_current_entry():
	entries = [
		_fake_entry("same", options_token="token-same"),
		_fake_entry("other", options_token="token-other"),
	]
	hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _domain: entries))

	assert opt_token_in_use(hass, "token-same", exclude_entry_id="same") is False
	assert opt_token_in_use(hass, "token-other", exclude_entry_id="same") is True


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

