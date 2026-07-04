"""Test that stationary timer doesn't cause threading errors."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeHass:
    def __init__(self):
        self._tasks = []
        self.data = {}
        self.states = self.States()
        self.services = self.Services(self)
        self.loop = self.Loop()

    def async_create_task(self, coro):
        self._tasks.append(coro)

    class Loop:
        def time(self):
            return 0.0

        def call_at(self, when, callback, *args):
            """Mock loop.call_at - returns a cancellable handle."""
            handle = MagicMock()
            return handle

    class Services:
        def __init__(self, parent):
            self.parent = parent

        async def async_call(self, domain, service, data):
            pass

    class States:
        def __init__(self):
            self._states = {}

        def async_set(self, entity_id, state, attributes=None):
            class FakeState:
                def __init__(self, state_val, attrs):
                    self.state = state_val
                    self.attributes = attrs or {}
            self._states[entity_id] = FakeState(state, attributes)

        def get(self, entity_id):
            if entity_id in self._states:
                return self._states[entity_id]
            return None


class FakeStore:
    def __init__(self):
        self.data = {}

    async def async_load(self):
        return self.data.copy() if self.data else None

    async def async_save(self, data):
        self.data = data.copy()


def make_event(new_state_obj, old_state_obj=None):
    """Create a mock event object matching Home Assistant's event format."""
    class MockEvent:
        def __init__(self, ns, os):
            self.data = {
                "entity_id": ns.entity_id if ns else "device_tracker.test",
                "new_state": ns,
                "old_state": os,
            }
    return MockEvent(new_state_obj, old_state_obj)


def make_state(entity_id, state, attributes):
    """Create a mock state object."""
    class MockState:
        def __init__(self, eid, st, attrs):
            self.entity_id = eid
            self.state = st
            self.attributes = attrs
    return MockState(entity_id, state, attributes)


@pytest.mark.asyncio
async def test_stationary_timer_thread_safety():
    """Test that timer callback doesn't cause threading errors."""
    hass = FakeHass()

    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 0,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
        }
    }

    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    await coordinator.async_load()

    # Mock device tracker state
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
            "gps_accuracy": 10,
        }
    )

    # Mock notification service
    with patch.object(coordinator, '_async_send_notification', new_callable=AsyncMock):
        # Create a mock event with new state
        new_state = make_state(
            "device_tracker.test",
            "home",
            {
                "latitude": 45.1234567,
                "longitude": 9.1234567,
                "gps_accuracy": 10,
            }
        )
        event = make_event(new_state)

        # Call _handle_device_event which creates the timer
        await coordinator._handle_device_event(event)

        # Verify timer was created
        assert coordinator._stationary_handle is not None, "Timer should be created"
        # stationary_count=0: counter stays at 0 (immediate alarm mode, no counting)
        assert coordinator._stationary_counter == 0, "Counter should be 0 when stationary_count=0"

        # The timer should be callable
        assert callable(coordinator._stationary_handle), "Timer handle should be callable"


@pytest.mark.asyncio
async def test_stationary_timer_execution():
    """Test that timer actually executes and activates alarm."""
    hass = FakeHass()

    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 0,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
            "debug_mode": True,
        }
    }

    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    await coordinator.async_load()

    # Mock device tracker state
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
            "gps_accuracy": 10,
            "source_type": "gps",
        }
    )

    notification_sent = False

    async def mock_notify(*args, **kwargs):
        nonlocal notification_sent
        notification_sent = True

    with patch.object(coordinator, '_async_send_notification', side_effect=mock_notify):
        # Simulate GPS update
        new_state = make_state(
            "device_tracker.test",
            "home",
            {
                "latitude": 45.1234567,
                "longitude": 9.1234567,
                "gps_accuracy": 10,
                "source_type": "gps",
            }
        )
        event = make_event(new_state)

        await coordinator._handle_device_event(event)

        # Verify initial state
        assert coordinator._stationary_handle is not None
        assert coordinator.alarm_active is False

        # Fast-forward time and trigger the timer manually
        if coordinator._stationary_handle:
            # Call _stationary_check directly (simulating timer expiration)
            await coordinator._stationary_check(45.1234567, 9.1234567)

        # After timer expiration with count=0, alarm should activate
        assert coordinator.alarm_active is True, "Alarm should be active after timer expires"
        assert coordinator.saved_latitude == 45.1234567
        assert coordinator.saved_longitude == 9.1234567
        assert notification_sent is True, "Notification should be sent"


@pytest.mark.asyncio
async def test_timer_cancellation_on_movement():
    """Test that timer is cancelled when vehicle moves."""
    hass = FakeHass()

    config = {
        "device_tracker": "device_tracker.test",
        "options": {
            "person_entity": "person.test",
            "notifier": "test",
            "activation_mode": "position",
            "stationary_minutes": 1,
            "stationary_count": 3,
            "tolerance_radius": 50,
            "webhook_token": "test_token",
        }
    }

    coordinator = VehicleCoordinator(hass, "test_entry", config)
    coordinator.store = FakeStore()
    await coordinator.async_load()

    # Set initial position
    hass.states.async_set(
        "device_tracker.test",
        "home",
        {
            "latitude": 45.1234567,
            "longitude": 9.1234567,
        }
    )

    # First GPS - starts timer
    event1 = make_event(make_state("device_tracker.test", "home", {
        "latitude": 45.1234567,
        "longitude": 9.1234567,
    }))
    await coordinator._handle_device_event(event1)
    first_handle = coordinator._stationary_handle
    assert first_handle is not None
    assert coordinator._stationary_counter == 1

    # Second GPS - same position, timer continues
    event2 = make_event(make_state("device_tracker.test", "home", {
        "latitude": 45.1234567,
        "longitude": 9.1234567,
    }))
    await coordinator._handle_device_event(event2)
    second_handle = coordinator._stationary_handle
    assert second_handle == first_handle, "Timer should not restart for same position"
    assert coordinator._stationary_counter == 2

    # Third GPS - moved outside tolerance (>50m), timer should restart
    # ~0.001 degrees latitude ≈ 111m, so 45.1244 is ~100m from 45.1234
    event3 = make_event(make_state("device_tracker.test", "home", {
        "latitude": 45.1244567,
        "longitude": 9.1234567,
    }))
    await coordinator._handle_device_event(event3)
    third_handle = coordinator._stationary_handle
    # Counter should reset to 1, and we should have a new timer
    assert coordinator._stationary_counter == 1, "Counter should reset on movement"
    # Timer should be recreated (new callback function)
    assert third_handle is not None, "New timer should be created"
