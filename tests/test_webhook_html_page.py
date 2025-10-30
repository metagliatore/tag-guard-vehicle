"""Tests for webhook HTML page (GET handler) to improve coverage."""
import pytest
from unittest.mock import MagicMock
from aiohttp import web


@pytest.mark.asyncio
async def test_webhook_get_returns_html_page():
    """Test that GET request to webhook returns an HTML page."""
    from custom_components.tag_guard_vehicle.services import handle_webhook_impl

    class FakeHass:
        pass

    class FakeCoordinator:
        def __init__(self):
            self.alarm_active = False
            self.config = {"device_tracker": "device.tracker_test"}

        async def set_alarm_active(self, active):
            self.alarm_active = active

        async def async_save(self):
            pass

    # Create a mock request for GET
    request = MagicMock(spec=web.Request)
    request.method = "GET"
    request.query = {}

    hass = FakeHass()
    coordinator = FakeCoordinator()
    device_tracker = "device.tracker_test"

    # Call the webhook handler
    response = await handle_webhook_impl(hass, coordinator, device_tracker, request)

    # Verify response is HTML
    assert isinstance(response, web.Response)
    assert response.status == 200
    assert "text/html" in response.content_type

    # Verify HTML contains some expected content
    html_body = response.body.decode("utf-8")
    assert len(html_body) > 0
    # Check for basic HTML structure
    assert "<" in html_body and ">" in html_body
