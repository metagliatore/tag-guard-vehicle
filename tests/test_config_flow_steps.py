"""Tests the user-facing steps of the config flow.

These tests exercise the step sequencing and form contents presented to the user
during integration setup.
"""

import pytest

from custom_components.tag_guard_vehicle.config_flow import TagGuardVehicleConfigFlow
from custom_components.tag_guard_vehicle.const import (
    CONF_DEVICE_TRACKER,
    CONF_PERSON_ENTITY,
    CONF_NOTIFIER,
    CONF_TOLERANCE_RADIUS,
    CONF_ACTIVATION_MODE,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
)


@pytest.mark.asyncio
# Test: initial user step presents the user form
async def test_flow_user_shows_form():
    flow = TagGuardVehicleConfigFlow()
    res = await flow.async_step_user()
    assert res["type"] == "form" and res["step_id"] == "user"


@pytest.mark.asyncio
# Test: choosing position activation mode branches flow to stationary step
async def test_flow_user_branches_to_stationary(monkeypatch):
    flow = TagGuardVehicleConfigFlow()
    user_input = {
        CONF_DEVICE_TRACKER: "device.tracker_1",
        CONF_PERSON_ENTITY: "person.someone",
        CONF_NOTIFIER: "notify.test",
        CONF_TOLERANCE_RADIUS: 200,
        CONF_ACTIVATION_MODE: "position",
        "tag_model": "model_a",
        "debug_mode": False,
    }
    res = await flow.async_step_user(user_input)
    assert res["type"] == "form" and res["step_id"] == "stationary"


@pytest.mark.asyncio
# Test: completing the flow produces a webhook token and creates the entry
async def test_flow_complete_shows_token_and_creates_entry(monkeypatch):
    # make token deterministic
    monkeypatch.setattr("secrets.token_urlsafe", lambda n: "fixed-token")
    flow = TagGuardVehicleConfigFlow()
    user_input = {
        CONF_DEVICE_TRACKER: "device.tracker_1",
        CONF_PERSON_ENTITY: "person.someone",
        CONF_NOTIFIER: "notify.test",
        CONF_TOLERANCE_RADIUS: 200,
        CONF_ACTIVATION_MODE: "connection",
        "tag_model": "model_a",
        "debug_mode": False,
    }
    # user step -> since activation=connection, it should go to show_token
    res = await flow.async_step_user(user_input)
    assert res["type"] == "form" and res["step_id"] == "show_token"
    
    # show_token step has no input fields - just description and Submit button
    # User confirms by passing empty dict (no fields to fill)
    res2 = await flow.async_step_show_token({})
    assert res2["type"] == "create_entry"
    assert res2["options"]["webhook_token"] == "fixed-token"
