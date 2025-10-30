"""Helpers for config flow: validate payload and options creation.
"""

from custom_components.tag_guard_vehicle.utils import needs_stationary_step, build_create_payload
from custom_components.tag_guard_vehicle.const import (
    CONF_DEVICE_TRACKER,
    CONF_ACTIVATION_MODE,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
)


# Test: needs_stationary_step returns True for activation modes that require stationary checks
def test_needs_stationary_step():
    assert needs_stationary_step("position")
    assert needs_stationary_step("combined")
    assert not needs_stationary_step("connection")


# Test: build_create_payload emits defaults and generates a webhook token when absent
def test_build_create_payload_defaults(monkeypatch):
    # control token generation to deterministic value
    monkeypatch.setattr("secrets.token_urlsafe", lambda n: "fixedtoken")
    ui = {CONF_DEVICE_TRACKER: "device.tracker_1", CONF_ACTIVATION_MODE: "position"}
    data, options = build_create_payload(ui)
    assert data[CONF_DEVICE_TRACKER] == "device.tracker_1"
    assert options["webhook_token"] == "fixedtoken"


# Test: build_create_payload merges provided base config and respects stationary fields
def test_build_create_payload_with_base_and_stationary(monkeypatch):
    monkeypatch.setattr("secrets.token_urlsafe", lambda n: "fixedtoken")
    base = {CONF_DEVICE_TRACKER: "device.tracker_base", CONF_ACTIVATION_MODE: "combined"}
    ui = {CONF_STATIONARY_MINUTES: 5, CONF_STATIONARY_COUNT: 4}
    data, options = build_create_payload(ui, base=base)
    assert data[CONF_DEVICE_TRACKER] == "device.tracker_base"
    assert options["webhook_token"] == "fixedtoken"
    assert options["stationary_minutes"] == 5
    assert options["stationary_count"] == 4
