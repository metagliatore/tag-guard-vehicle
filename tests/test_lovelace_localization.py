import pytest

from custom_components.tag_guard_vehicle.utils import async_build_notify_message, translate


class FakeHass:
	pass


@pytest.mark.asyncio
async def test_translate_falls_back_to_default_without_ha_translation_context():
	hass = FakeHass()
	text = await translate(hass, "messages.any_key", "fallback")
	assert text == "fallback"


@pytest.mark.asyncio
async def test_async_build_notify_message_contains_map_urls_in_fallback_mode():
	hass = FakeHass()
	title, message = await async_build_notify_message(hass, 45.5, 9.2, 45.4, 9.1)

	assert title
	assert "https://maps.google.com/?q=45.5,9.2" in message
	assert "https://maps.google.com/?q=45.4,9.1" in message

