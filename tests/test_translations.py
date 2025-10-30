"""Tests translate() helper and ensures translation JSONs are valid.

These tests exercise the translation fallbacks used when Home Assistant
translation APIs are not available in the test environment.
"""

import json
import os
import asyncio

import pytest

from custom_components.tag_guard_vehicle import utils

HERE = os.path.dirname(__file__)
TRANS_DIR = os.path.join(os.path.dirname(HERE), "custom_components", "tag_guard_vehicle", "translations")


def test_translate_fallback_without_hass():
    # calling translate with hass=None should return the provided default string
    res = asyncio.run(utils.translate(None, "messages.some_missing_key", "fallback text"))
    assert res == "fallback text"


def test_async_build_notify_message_without_hass():
    # async_build_notify_message should fall back to English defaults when hass is None
    title, message = asyncio.run(utils.async_build_notify_message(None, 1.23, 4.56))
    assert isinstance(title, str) and len(title) > 0
    assert "maps.google.com" in message or "{lat}" in message


def test_translation_jsons_valid_and_have_component_node():
    # ensure each locale JSON file loads and contains a top-level 'component' key
    files = [f for f in os.listdir(TRANS_DIR) if f.endswith('.json')]
    assert files, "No translation JSON files found"
    for f in files:
        path = os.path.join(TRANS_DIR, f)
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        assert isinstance(data, dict), f"{f} did not parse as JSON dict"
        # Home Assistant translations typically have a top-level language code mapping to component.
        # For our simple check, accept either top-level 'component' or nested under a language code.
        if 'component' in data:
            comp = data['component']
        else:
            # pick first language
            first = next(iter(data.values()))
            comp = first.get('component') if isinstance(first, dict) else None
        assert comp is not None, f"{f} missing 'component' node"
