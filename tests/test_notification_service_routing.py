"""Tests for generic notification service routing."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class _FakeStore:
    async def async_load(self):
        return None

    async def async_save(self, _data):
        return None


class _FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data):
        self.calls.append((domain, service, data))


class _FakeHass:
    def __init__(self):
        self.services = _FakeServices()


@pytest.mark.asyncio
async def test_send_notification_notify_domain_legacy_and_prefixed():
    hass = _FakeHass()
    coordinator = VehicleCoordinator(hass, "entry_1", {"device_tracker": "device_tracker.test", "notifier": "notify.mobile_app_phone"})
    coordinator.store = _FakeStore()

    await coordinator._async_send_notification("Title", "Body")

    assert len(hass.services.calls) == 1
    domain, service, payload = hass.services.calls[0]
    assert domain == "notify"
    assert service == "mobile_app_phone"
    assert payload["title"] == "Title"
    assert payload["message"] == "Body"


@pytest.mark.asyncio
async def test_send_notification_notify_adds_map_click_data_when_map_url_present():
    hass = _FakeHass()
    coordinator = VehicleCoordinator(hass, "entry_1", {"device_tracker": "device_tracker.test", "notifier": "notify.mobile_app_phone"})
    coordinator.store = _FakeStore()

    await coordinator._async_send_notification("Title", "Body", map_url="https://maps.google.com/?q=45,9")

    assert len(hass.services.calls) == 1
    domain, service, payload = hass.services.calls[0]
    assert domain == "notify"
    assert service == "mobile_app_phone"
    assert payload["data"]["url"] == "https://maps.google.com/?q=45,9"
    assert payload["data"]["clickAction"] == "https://maps.google.com/?q=45,9"


@pytest.mark.asyncio
async def test_send_notification_telegram_service_with_config_entry_id_query():
    hass = _FakeHass()
    coordinator = VehicleCoordinator(
        hass,
        "entry_1",
        {
            "device_tracker": "device_tracker.test",
            "notifier": "telegram_bot.send_message?config_entry_id=01ABCDEF000000000000000000",
        },
    )
    coordinator.store = _FakeStore()

    await coordinator._async_send_notification("Attenzione", "Qualcuno ha cambiato stato")

    assert len(hass.services.calls) == 1
    domain, service, payload = hass.services.calls[0]
    assert domain == "telegram_bot"
    assert service == "send_message"
    assert payload["config_entry_id"] == "01ABCDEF000000000000000000"
    assert payload["message"].startswith("Attenzione")
    assert "title" not in payload

