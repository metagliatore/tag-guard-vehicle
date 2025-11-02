"""Tests for webhook GET handler (HTML control page)."""
import asyncio
import pytest
from aiohttp import web
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_webhook_get_returns_html_control_page():
    """Test that GET request to webhook returns HTML control page."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for GET
    request = MagicMock(spec=web.Request)
    request.method = "GET"
    request.query = {}

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify response is HTML
    assert isinstance(response, web.Response)
    assert response.status == 200
    assert response.content_type == "text/html"

    # Verify HTML contains control buttons
    html_body = response.body.decode("utf-8")
    assert "Tag Guard Vehicle" in html_body
    assert "Start" in html_body or "start" in html_body.lower()
    assert "Stop" in html_body or "stop" in html_body.lower()
    assert "button" in html_body.lower() or "form" in html_body.lower()


@pytest.mark.asyncio
async def test_webhook_get_with_action_query_param_start():
    """Test POST request with action=start in JSON body."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with action=start in JSON body
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}
    request.json = AsyncMock(return_value={"action": "start"})

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify alarm was started
    assert coordinator.alarm_active is True
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_get_with_action_query_param_stop():
    """Test POST request with action=stop in JSON body."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = True

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with action=stop in JSON body
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}
    request.json = AsyncMock(return_value={"action": "stop"})

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify alarm was stopped
    assert coordinator.alarm_active is False
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_post_json_with_action_start():
    """Test POST with JSON body containing action=enable."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with JSON
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}

    async def fake_json():
        return {"action": "start"}

    request.json = fake_json

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify alarm was started
    assert coordinator.alarm_active is True
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_post_json_with_action_stop():
    """Test POST with JSON body containing action=stop."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = True

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with JSON
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}

    async def fake_json():
        return {"action": "stop"}

    request.json = fake_json

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify alarm was stopped
    assert coordinator.alarm_active is False
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_post_with_coordinates():
    """Test POST with action=save uses device_tracker coordinates (not payload)."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeState:
        def __init__(self):
            self.attributes = {"latitude": 45.789, "longitude": 9.123}

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return FakeState()

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test", "webhook_token": "test_token"}
            self.alarm_active = False
            self.saved_latitude = None
            self.saved_longitude = None

        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = lat
            self.saved_longitude = lon

        async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
            # For tests, just save immediately (ignore freshness check)
            await self._async_save_position(lat, lon, reason=reason)

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with action=save in JSON body
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}

    async def fake_json():
        # Action in body, coordinates should be ignored (SAVE uses device_tracker)
        return {"action": "save", "latitude": 45.123, "longitude": 9.456}

    request.json = fake_json

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify coordinates from device_tracker were used (not from payload)
    assert coordinator.saved_latitude == 45.789
    assert coordinator.saved_longitude == 9.123
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_post_without_coordinates_uses_device_tracker():
    """Test POST with action=save uses device_tracker coordinates."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeState:
        def __init__(self):
            self.attributes = {"latitude": 45.789, "longitude": 9.012, "ops": []}

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                if entity_id == "device.tracker_test":
                    return FakeState()
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False
            self.saved_latitude = None
            self.saved_longitude = None

        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = lat
            self.saved_longitude = lon

        async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
            # For tests, just save immediately (ignore freshness check)
            await self._async_save_position(lat, lon, reason=reason)

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for POST with action=save in JSON body
    request = MagicMock(spec=web.Request)
    request.method = "POST"
    request.query = {}

    async def fake_json():
        return {"action": "save"}  # Action in body, no coordinates

    request.json = fake_json

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify coordinates from device_tracker were used
    assert coordinator.saved_latitude == 45.789
    assert coordinator.saved_longitude == 9.012
    assert response.status == 200


@pytest.mark.asyncio
async def test_webhook_html_page_structure():
    """Test that HTML page contains expected elements."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return None

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = True

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for GET
    request = MagicMock(spec=web.Request)
    request.method = "GET"
    request.query = {}

    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(coordinator.hass, coordinator, device_tracker, request)

    # Verify response structure
    html_body = response.body.decode("utf-8")

    # Check for HTML structure
    assert "<html" in html_body.lower()
    assert "<head" in html_body.lower()
    assert "<body" in html_body.lower()

    # Check for title or heading
    assert "vehicle" in html_body.lower() or "parking" in html_body.lower() or "guard" in html_body.lower()

    # Check for some form of control elements (buttons or links)
    # The implementation might use different approaches
    has_controls = any(
        [
            "<button" in html_body.lower(),
            "<form" in html_body.lower(),
            "?action=" in html_body,
            'href="' in html_body.lower(),
        ]
    )
    assert has_controls, "HTML page should contain some control elements (buttons, forms, or action links)"


@pytest.mark.asyncio
async def test_webhook_save_with_require_fresh_position_parameter():
    """Test POST with action=save accepts require_fresh_position parameter."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeState:
        def __init__(self):
            self.attributes = {"latitude": 45.789, "longitude": 9.123}

    class FakeHass:
        def async_create_task(self, coro):
            pass

        class Services:
            async def async_call(self, domain, service, data):
                pass

        services = Services()

        class States:
            def get(self, entity_id):
                return FakeState()

        states = States()

    class FakeCoordinator:
        def __init__(self):
            self.hass = FakeHass()
            self.config = {"device_tracker": "device.tracker_test"}
            self.alarm_active = False
            self.saved_latitude = None
            self.saved_longitude = None
            self.require_fresh_called_with = None

        async def _async_save_position(self, lat, lon, **kwargs):
            self.saved_latitude = lat
            self.saved_longitude = lon

        async def _async_save_position_with_freshness_check(self, lat, lon, require_fresh_position=True, notify_waiting=False, reason="save"):
            # Track what parameter was passed
            self.require_fresh_called_with = require_fresh_position
            await self._async_save_position(lat, lon, reason=reason)

        async def set_alarm_active(self, active, activation_time=None, notify_waiting=False):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Test with require_fresh_position=True (default)
    request1 = MagicMock(spec=web.Request)
    request1.method = "POST"
    request1.query = {}
    async def fake_json1():
        return {"action": "save"}
    request1.json = fake_json1

    coordinator1 = FakeCoordinator()
    response1 = await handle_webhook_impl(coordinator1.hass, coordinator1, "device.tracker_test", request1)
    
    assert response1.status == 200
    assert coordinator1.require_fresh_called_with == True  # Default

    # Test with require_fresh_position=False
    request2 = MagicMock(spec=web.Request)
    request2.method = "POST"
    request2.query = {}
    async def fake_json2():
        return {"action": "save", "require_fresh_position": False}
    request2.json = fake_json2

    coordinator2 = FakeCoordinator()
    response2 = await handle_webhook_impl(coordinator2.hass, coordinator2, "device.tracker_test", request2)
    
    assert response2.status == 200
    assert coordinator2.require_fresh_called_with == False

    # Test with require_fresh_position=True (explicit)
    request3 = MagicMock(spec=web.Request)
    request3.method = "POST"
    request3.query = {}
    async def fake_json3():
        return {"action": "save", "require_fresh_position": True}
    request3.json = fake_json3

    coordinator3 = FakeCoordinator()
    response3 = await handle_webhook_impl(coordinator3.hass, coordinator3, "device.tracker_test", request3)
    
    assert response3.status == 200
    assert coordinator3.require_fresh_called_with == True
