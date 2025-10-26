"""Tests helper utilities for the options flow.

These validate option payload merging and helper functions used by the
options flow steps.
"""

import pytest

from custom_components.vehicle_bt_parking_sentinel.utils import merge_options, needs_stationary_step
from custom_components.vehicle_bt_parking_sentinel.options_flow import VehicleBtParkingSentinelOptionsFlowHandler
from custom_components.vehicle_bt_parking_sentinel.const import (
    CONF_ACTIVATION_MODE,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
)


class FakeConfigEntry:
    def __init__(self, options=None):
        self.options = options or {}


# Verify merge_options correctly overrides existing options with user input
def test_merge_options_simple():
    base = {"a": 1, "b": 2}
    ui = {"b": 3, "c": 4}
    merged = merge_options(base, ui)
    assert merged == {"a": 1, "b": 3, "c": 4}


@pytest.mark.asyncio
@pytest.mark.asyncio
# Options flow initial step branches to stationary when activation requires it
async def test_options_flow_init_branches_to_stationary_when_needed():
    entry = FakeConfigEntry(options={})
    flow = VehicleBtParkingSentinelOptionsFlowHandler(entry)
    user_input = {CONF_ACTIVATION_MODE: "combined"}
    result = await flow.async_step_init(user_input)
    # should be showing the stationary form
    assert result["type"] == "form"
    assert result["step_id"] == "stationary"


@pytest.mark.asyncio
@pytest.mark.asyncio
# Stationary step merges inputs and completes the options flow
async def test_options_flow_stationary_merges_and_finishes():
    entry = FakeConfigEntry(options={"existing": True})
    flow = VehicleBtParkingSentinelOptionsFlowHandler(entry)
    # simulate prior _user_input set by initial step
    flow._user_input = {"a": 1}
    user_input = {CONF_STATIONARY_MINUTES: 7, CONF_STATIONARY_COUNT: 2}
    result = await flow.async_step_stationary(user_input)
    assert result["type"] == "create_entry"
    assert result["data"][CONF_STATIONARY_MINUTES] == 7
    assert result["data"][CONF_STATIONARY_COUNT] == 2
