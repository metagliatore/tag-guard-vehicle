"""Test webhook routing with multiple connection mode instances.

Verifies that webhooks are correctly routed to the right instance
when multiple vehicles are configured in connection mode.
"""
import pytest


@pytest.mark.asyncio
async def test_webhook_routing_multiple_connection_mode_instances():
    """Test that webhook commands are routed to correct instance with multiple connection mode vehicles."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            self._tasks.append(coro)

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                # Return different coordinates based on entity_id
                # Use future GPS timestamp to ensure freshness check passes
                from datetime import datetime, timedelta
                future_time = datetime.now() + timedelta(hours=1)
                gps_timestamp = future_time.strftime("%Y%m%d%H%M%S")
                
                class FakeState:
                    def __init__(self, lat, lon, gps_ts):
                        self.attributes = {
                            "ops": [
                                {
                                    "oprnType": "LOCATION",
                                    "latitude": str(lat),
                                    "longitude": str(lon),
                                    "extra": {"gpsUtcDt": gps_ts},
                                }
                            ],
                            "latitude": lat,
                            "longitude": lon,
                            "gpsUtcDt": gps_ts,
                        }
                
                if entity_id == "device.tracker_car":
                    return FakeState(45.1, 9.1, gps_timestamp)
                elif entity_id == "device.tracker_motorcycle":
                    return FakeState(45.2, 9.2, gps_timestamp)
                return None

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    class FakeRequest:
        def __init__(self, action, **kwargs):
            self.method = "POST"
            self.query = {}
            self.headers = {}
            self._action = action
            self._kwargs = kwargs

        async def json(self):
            data = {"action": self._action}
            data.update(self._kwargs)
            return data

    hass = FakeHass()

    # Create two connection mode instances
    config_car = {
        "device_tracker": "device.tracker_car",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord_car = VehicleCoordinator(hass, "entry_car", config_car)
    coord_car.store = FakeStore()
    coord_car.alarm_active = False

    config_motorcycle = {
        "device_tracker": "device.tracker_motorcycle",
        "activation_mode": "connection",
        "tag_model": "samsung_smarttag2",
    }
    coord_motorcycle = VehicleCoordinator(hass, "entry_motorcycle", config_motorcycle)
    coord_motorcycle.store = FakeStore()
    coord_motorcycle.alarm_active = False

    # Send START command to car webhook (skip GPS freshness check for this test)
    request_car_start = FakeRequest("start", require_fresh_position=False)
    response_car = await handle_webhook_impl(
        hass, coord_car, "device.tracker_car", request_car_start
    )

    # Verify only car is affected
    assert response_car.status == 200
    assert coord_car.alarm_active is True, "Car alarm should be activated"
    assert coord_car.saved_latitude == 45.1
    assert coord_motorcycle.alarm_active is False, "Motorcycle should be unchanged"
    assert coord_motorcycle.saved_latitude is None

    # Send START command to motorcycle webhook (skip GPS freshness check for this test)
    request_motorcycle_start = FakeRequest("start", require_fresh_position=False)
    response_motorcycle = await handle_webhook_impl(
        hass, coord_motorcycle, "device.tracker_motorcycle", request_motorcycle_start
    )

    # Verify both are now active independently
    assert response_motorcycle.status == 200
    assert coord_car.alarm_active is True, "Car alarm should still be active"
    assert coord_car.saved_latitude == 45.1, "Car position unchanged"
    assert coord_motorcycle.alarm_active is True, "Motorcycle alarm should be activated"
    assert coord_motorcycle.saved_latitude == 45.2

    # Send STOP command to car only
    request_car_stop = FakeRequest("stop")
    response_car_stop = await handle_webhook_impl(
        hass, coord_car, "device.tracker_car", request_car_stop
    )

    # Verify only car is stopped
    assert response_car_stop.status == 200
    assert coord_car.alarm_active is False, "Car alarm should be deactivated"
    assert coord_car.saved_latitude == 45.1, "Car position preserved"
    assert coord_motorcycle.alarm_active is True, "Motorcycle alarm should still be active"
    assert coord_motorcycle.saved_latitude == 45.2, "Motorcycle position unchanged"


@pytest.mark.asyncio
async def test_connection_mode_concurrent_disconnect_events():
    """Test that concurrent disconnect events for multiple vehicles are handled correctly."""
    from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator
    import asyncio

    class FakeHass:
        def __init__(self):
            self._tasks = []
            self.data = {}

        def async_create_task(self, coro):
            task = asyncio.create_task(coro)
            self._tasks.append(task)
            return task

        class Services:
            def __init__(self):
                self.calls = []

            async def async_call(self, domain, service, data):
                self.calls.append((domain, service, data))

        class States:
            def get(self, entity_id):
                return None

        services = Services()
        states = States()

    class FakeStore:
        async def async_load(self):
            return None

        async def async_save(self, data):
            pass

    hass = FakeHass()

    # Create multiple instances
    vehicles = ["car", "motorcycle", "bicycle", "scooter"]
    coordinators = []

    for vehicle in vehicles:
        config = {
            "device_tracker": f"device.tracker_{vehicle}",
            "activation_mode": "connection",
            "tag_model": "samsung_smarttag2",
        }
        coord = VehicleCoordinator(hass, f"entry_{vehicle}", config)
        coord.store = FakeStore()
        coord.last_tag_state = "connected"
        coord.alarm_active = False
        coordinators.append((coord, vehicle))

    # Create disconnect events for all vehicles
    class FakeState:
        def __init__(self, entity_id, lat, lon):
            self.entity_id = entity_id
            self.attributes = {
                "ops": [
                    {
                        "oprnType": "LOCATION",
                        "latitude": str(lat),
                        "longitude": str(lon),
                        "extra": {"gpsUtcDt": "20251102200000"},
                    },
                    {"oprnType": "CHECK_CONNECTION", "battery": "LOW"},
                ],
                "latitude": lat,
                "longitude": lon,
                "gpsUtcDt": "20251102200000",
            }

    class FakeEvent:
        def __init__(self, entity_id, lat, lon):
            self.data = {
                "new_state": FakeState(entity_id, lat, lon),
                "old_state": None,
                "entity_id": entity_id,
            }

    # Process all disconnect events concurrently
    positions = [(45.1, 9.1), (45.2, 9.2), (45.3, 9.3), (45.4, 9.4)]
    tasks = []

    for (coord, vehicle), (lat, lon) in zip(coordinators, positions):
        event = FakeEvent(f"device.tracker_{vehicle}", lat, lon)
        task = coord._handle_device_event(event)
        tasks.append(task)

    # Wait for all events to be processed
    await asyncio.gather(*tasks)

    # Verify each coordinator has correct independent state
    for (coord, vehicle), (lat, lon) in zip(coordinators, positions):
        assert coord.last_tag_state == "disconnected", f"{vehicle} should be disconnected"
        assert coord.alarm_active is True, f"{vehicle} alarm should be active"
        assert coord.saved_latitude == lat, f"{vehicle} should have correct latitude"
        assert coord.saved_longitude == lon, f"{vehicle} should have correct longitude"
        assert coord.entry_id == f"entry_{vehicle}", f"{vehicle} should have correct entry_id"

    print(f"✅ Successfully processed {len(coordinators)} concurrent disconnect events")
