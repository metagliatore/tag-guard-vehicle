import pytest

from custom_components.tag_guard_vehicle import async_get_options_flow, async_setup
from custom_components.tag_guard_vehicle.const import DOMAIN


class FakeHass:
	def __init__(self):
		self.data = {}


class FakeConfigEntry:
	pass


@pytest.mark.asyncio
async def test_async_setup_initializes_domain_and_coordinator_registry():
	hass = FakeHass()

	result = await async_setup(hass, {})

	assert result is True
	assert DOMAIN in hass.data
	assert "coordinators" in hass.data[DOMAIN]
	assert hass.data[DOMAIN]["coordinators"] == {}


@pytest.mark.asyncio
async def test_async_get_options_flow_returns_handler():
	flow = await async_get_options_flow(FakeConfigEntry())
	assert flow is not None
	assert flow.__class__.__name__ == "TagGuardVehicleOptionsFlowHandler"

