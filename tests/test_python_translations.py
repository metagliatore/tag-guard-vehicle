import asyncio
import types
from unittest.mock import patch

from custom_components.tag_guard_vehicle import utils


async def _fake_get_translations(hass, domain):
    # return mapping for language 'en' with component.messages keys
    return {
        'en': {
            'component': {
                'messages': {
                    'moved_title': 'MOVED TITLE (EN)',
                    'moved_message': 'MOVED MESSAGE {lat} {lon}',
                }
            }
        }
    }


def test_translate_uses_translations_when_present():
    # patch the translation loader
    with patch('homeassistant.helpers.translation.async_get_translations', new=_fake_get_translations):
        title = asyncio.run(utils.translate(types.SimpleNamespace(config=types.SimpleNamespace(language='en')), 'messages.moved_title', 'fallback'))
        assert title == 'MOVED TITLE (EN)'


def test_async_build_notify_message_uses_translations():
    with patch('homeassistant.helpers.translation.async_get_translations', new=_fake_get_translations):
        title, message = asyncio.run(utils.async_build_notify_message(types.SimpleNamespace(config=types.SimpleNamespace(language='en')), 12.34, 56.78))
        assert title == 'MOVED TITLE (EN)'
        assert 'MOVED MESSAGE' in message


def test_translate_falls_back_when_missing_key():
    with patch('homeassistant.helpers.translation.async_get_translations', new=_fake_get_translations):
        res = asyncio.run(utils.translate(types.SimpleNamespace(config=types.SimpleNamespace(language='en')), 'messages.some_missing_key', 'fallback text'))
        assert res == 'fallback text'
