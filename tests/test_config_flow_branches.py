from types import SimpleNamespace

import pytest

from custom_components.tag_guard_vehicle.config_flow import TagGuardVehicleConfigFlow
from custom_components.tag_guard_vehicle.const import (
    CONF_ACTIVATION_MODE,
    CONF_DEVICE_TRACKER,
    CONF_NOTIFIER,
    CONF_PERSON_ENTITY,
    CONF_STATIONARY_COUNT,
    CONF_STATIONARY_MINUTES,
    CONF_TOLERANCE_RADIUS,
)


class FakeEntry:
    def __init__(self, entry_id, token=None):
        self.entry_id = entry_id
        self.options = {"webhook_token": token} if token else {}
        self.data = {}


class FakeConfigEntries:
    def __init__(self, entries=None):
        self._entries = entries or []

    def async_entries(self, domain):
        return self._entries


class FakeServices:
    def async_services(self):
        return {"notify": {"mobile_app_phone": {}, "persistent_notification": {}}}


class FakeHass:
    def __init__(self, entries=None, base_url="http://ha.local:8123"):
        self.config_entries = FakeConfigEntries(entries)
        self.services = FakeServices()
        self.config = SimpleNamespace(
            api=SimpleNamespace(base_url=base_url),
            external_url=None,
            internal_url=None,
        )

    async def async_add_executor_job(self, func):
        return func()


@pytest.mark.asyncio
async def test_async_step_user_debug_stub_parsing_branch(monkeypatch):
    flow = TagGuardVehicleConfigFlow()
    hass = FakeHass()

    async def fake_executor_job(_func):
        return "device_tracker.smarttag,person.test,mobile_app_phone,250,manual,samsung_smarttag2,mytoken,true"

    hass.async_add_executor_job = fake_executor_job
    flow.hass = hass

    monkeypatch.setattr("os.path.exists", lambda _p: True)

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_async_step_stationary_user_input_transitions_to_show_token():
    flow = TagGuardVehicleConfigFlow()
    flow.hass = FakeHass()
    flow._user_data = {
        CONF_DEVICE_TRACKER: "device_tracker.smarttag",
        CONF_PERSON_ENTITY: "person.test",
        CONF_NOTIFIER: "mobile_app_phone",
        CONF_TOLERANCE_RADIUS: 200,
        CONF_ACTIVATION_MODE: "position",
        "tag_model": "samsung_smarttag2",
        "debug_mode": False,
    }

    result = await flow.async_step_stationary(
        {
            CONF_STATIONARY_MINUTES: 10,
            CONF_STATIONARY_COUNT: 2,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "show_token"


@pytest.mark.asyncio
async def test_async_step_show_token_builds_webhook_url_and_creates_entry_title():
    flow = TagGuardVehicleConfigFlow()
    flow.hass = FakeHass(base_url="http://example:8123")
    flow._create_payload = (
        {"device_tracker": "device_tracker.smarttagscooter"},
        {"webhook_token": "abc123"},
    )

    form = await flow.async_step_show_token()
    assert form["type"] == "form"
    assert form["step_id"] == "show_token"
    assert "webhook_url" in form.get("description_placeholders", {})
    assert "/api/webhook/abc123" in form["description_placeholders"]["webhook_url"]

    created = await flow.async_step_show_token({})
    assert created["type"] == "create_entry"
    assert "Smarttagscooter" in created["title"]
