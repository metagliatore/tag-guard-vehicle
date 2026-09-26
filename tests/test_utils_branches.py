from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.tag_guard_vehicle import utils


def test_parse_ops_string_non_list_wrapped_and_iterable_and_invalid():
    assert utils.parse_ops('{"a": 1}') == [{"a": 1}]

    class IterableObj:
        def __iter__(self):
            return iter([{"x": 1}])

    assert utils.parse_ops(IterableObj()) == [{"x": 1}]

    class BadIterable:
        def __iter__(self):
            raise RuntimeError("boom")

    assert utils.parse_ops(BadIterable()) == []


def test_validate_token_fallback_branch_on_compare_digest_error(monkeypatch):
    import hmac

    monkeypatch.setattr(hmac, "compare_digest", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("nope")))
    assert utils.validate_token("a", "a") is True
    assert utils.validate_token("a", "b") is False


def test_haversine_distance_fallback_on_invalid_inputs(monkeypatch):
    # Triggers exception in math conversion and fallback branch
    import math

    monkeypatch.setattr(math, "radians", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    dist = utils.haversine_distance(1.0, 0.0, 0.0, 0.0)
    assert isinstance(dist, float)


def test_parse_connection_state_generic_with_attrs_fallback():
    connected, last_op = utils.parse_connection_state([], {"oprnType": "LOCATION", "oprnResultCode": "1200", "oprnStsCd": "2800"})
    assert connected is True
    assert last_op == {}


def test_extract_coords_from_ops_attrs_generic_paths():
    lat, lon = utils.extract_coords_from_ops_attrs({"extra": {"latitude": "45.5", "longitude": "9.2"}}, {})
    assert lat == "45.5"
    assert lon == "9.2"

    lat2, lon2 = utils.extract_coords_from_ops_attrs({}, {"latitude": 1.0, "longitude": 2.0})
    assert lat2 == 1.0
    assert lon2 == 2.0


def test_parse_connection_state_by_model_and_extract_by_model_fallbacks(monkeypatch):
    with patch("custom_components.tag_guard_vehicle.parsers.get_parser", return_value=None):
        connected, _ = utils.parse_connection_state_by_model("unknown", [], {"oprnType": "LOCATION", "oprnResultCode": "1200", "oprnStsCd": "2800"})
        assert connected is True

    with patch("custom_components.tag_guard_vehicle.parsers.get_parser", side_effect=RuntimeError("boom")):
        lat, lon = utils.extract_coords_from_ops_attrs_by_model("unknown", {"latitude": "45", "longitude": "9"}, {})
        assert lat == "45"
        assert lon == "9"


@pytest.mark.asyncio
async def test_translate_formats_and_handles_format_error():
    class FakeHass:
        config = SimpleNamespace(language="en")

    async def fake_get_translations(_hass, _pkg):
        return {
            "en": {
                "component": {
                    "messages": {
                        "sample": "Hello {name}",
                        "bad": "Hello {missing}",
                    }
                }
            }
        }

    with patch("homeassistant.helpers.translation.async_get_translations", side_effect=fake_get_translations):
        ok = await utils.translate(FakeHass(), "messages.sample", "fallback", name="User")
        bad = await utils.translate(FakeHass(), "messages.bad", "fallback", name="User")

    assert ok == "Hello User"
    # format error path returns unformatted text
    assert bad == "Hello {missing}"


@pytest.mark.asyncio
async def test_async_build_notify_message_formats_urls_and_distance():
    class FakeHass:
        config = SimpleNamespace(language="en")

    async def fake_translate(_hass, key, default=None, **_fmt):
        if key.endswith("moved_title"):
            return "Moved"
        return "Moved by {distance}m from {saved_url} to {current_url}"

    with patch("custom_components.tag_guard_vehicle.utils.translate", side_effect=fake_translate):
        title, message = await utils.async_build_notify_message(FakeHass(), 45.5, 9.2, 45.4, 9.1)

    assert title == "Moved"
    assert "https://maps.google.com/?q=45.4,9.1" in message
    assert "https://maps.google.com/?q=45.5,9.2" in message


def test_build_create_payload_base_stationary_count_preserved_and_action_normalize():
    data, options = utils.build_create_payload(
        {"device_tracker": "device_tracker.a", "activation_mode": "position"},
        base={"stationary_count": 7, "person_entity": "person.test", "notifier": "n"},
    )
    assert data["device_tracker"] == "device_tracker.a"
    assert options["stationary_count"] == 7
    assert utils.normalize_notification_action(None) == ""


def test_should_save_after_stationary_invalid_values_false():
    assert utils.should_save_after_stationary("x", 9.2, 45.5, 9.2, 200) is False
