"""Unit tests asserting sensor entity state transitions and attribute updates.
"""

import pytest

from custom_components.vehicle_bt_parking_sentinel.sensor import VehicleBtParkingSentinelSensor


class FakeEntry:
    def __init__(self, entry_id):
        self.entry_id = entry_id


class FakeCoordinator:
    def __init__(self):
        self.saved_latitude = None
        self.saved_longitude = None
        self.tolerance_radius = 200
        self.stationary_minutes = 1
        self._stationary_candidate = None
        self._stationary_counter = 0
        self.alarm_active = False  # Start with alarm disabled
        self.position_notified = False
        self.last_tag_state = None
        self.activation_mode = "position"
        self.debug_mode = False

    async def set_alarm_active(self, active: bool):
        self.alarm_active = bool(active)


class FakeHass:
    def __init__(self):
        self.data = {}


@pytest.mark.asyncio
# Test: sensor state transitions (unknown -> awaiting_position -> parked -> alarm_triggered)
async def test_sensor_states_and_attributes():
    hass = FakeHass()
    entry = FakeEntry("e1")
    coord = FakeCoordinator()
    hass.data["vehicle_bt_parking_sentinel"] = {entry.entry_id + "_coordinator": coord}

    sensor = VehicleBtParkingSentinelSensor(hass, entry)

    # initial unknown (no position, alarm disabled)
    assert sensor.state == "unknown"

    await sensor.async_update()
    assert sensor.state == "unknown"
    attrs = sensor.extra_state_attributes
    assert attrs["tolerance_radius_m"] == 200
    assert attrs["alarm_active"] is False
    
    # activate alarm without position -> awaiting_position
    coord.alarm_active = True
    await sensor.async_update()
    assert sensor.state == "awaiting_position"

    # set candidate -> still awaiting_position
    coord._stationary_candidate = (45.0, 9.0)
    coord._stationary_counter = 2
    await sensor.async_update()
    assert sensor.state == "awaiting_position"

    # set saved pos -> parked
    coord.saved_latitude = 45.0
    coord.saved_longitude = 9.0
    coord._stationary_candidate = None
    coord._stationary_counter = 0
    await sensor.async_update()
    assert sensor.state == "parked"

    # simulate alarm triggered (movement detected, position_notified set)
    coord.position_notified = True
    coord.alarm_active = True
    await sensor.async_update()
    assert sensor.state == "alarm_triggered"
    
    # stop alarm -> position_saved
    coord.alarm_active = False
    coord.position_notified = False
    await sensor.async_update()
    assert sensor.state == "position_saved"
