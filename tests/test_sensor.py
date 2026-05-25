import pytest

from custom_components.tag_guard_vehicle.const import DOMAIN
from custom_components.tag_guard_vehicle.sensor import TagGuardVehicleSensor


class FakeEntry:
	def __init__(self):
		self.entry_id = "entry_1"
		self.data = {"device_tracker": "device_tracker.smarttagscooter"}
		self.options = {}

	def add_update_listener(self, listener):
		return None


class FakeCoordinator:
	def __init__(self):
		self.saved_latitude = 45.5
		self.saved_longitude = 9.2
		self.saved_gpsUtcDt = "20250101000000"
		self.saved_last_seen = "2025-01-01T00:00:00+00:00"
		self.saved_location_type = "basic"
		self.tolerance_radius = 200
		self.stationary_minutes = 10
		self._stationary_counter = 2
		self._stationary_candidate = (45.5, 9.2)
		self.alarm_active = False
		self.position_notified = False
		self.last_tag_state = "connected"
		self.activation_mode = "position"
		self.debug_mode = False
		self._awaiting_activation_save = False
		self.config = {"device_tracker": "device_tracker.smarttagscooter"}
		self.person_entity = "person.test"
		self.notifier = "mobile_app"


class FakeHass:
	def __init__(self, coordinator):
		self.data = {DOMAIN: {"entry_1_coordinator": coordinator}}


@pytest.mark.asyncio
async def test_sensor_name_includes_device_tracker():
	coordinator = FakeCoordinator()
	sensor = TagGuardVehicleSensor(FakeHass(coordinator), FakeEntry())

	assert "device_tracker.smarttagscooter" in sensor.name


@pytest.mark.asyncio
async def test_sensor_state_position_saved_when_alarm_inactive_with_saved_position():
	coordinator = FakeCoordinator()
	sensor = TagGuardVehicleSensor(FakeHass(coordinator), FakeEntry())

	await sensor.async_update()

	assert sensor.state == "position_saved"
	assert sensor.extra_state_attributes["alarm_active"] is False


@pytest.mark.asyncio
async def test_sensor_state_awaiting_position_when_alarm_active_and_waiting():
	coordinator = FakeCoordinator()
	coordinator.alarm_active = True
	coordinator._awaiting_activation_save = True
	sensor = TagGuardVehicleSensor(FakeHass(coordinator), FakeEntry())

	await sensor.async_update()

	assert sensor.state == "awaiting_position"

