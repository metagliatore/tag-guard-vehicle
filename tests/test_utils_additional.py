from custom_components.tag_guard_vehicle.utils import (
	coerce_coords,
	format_map_url,
	merge_options,
	needs_stationary_step,
	normalize_notification_action,
	should_save_after_stationary,
)


def test_merge_options_user_input_overrides_existing():
	merged = merge_options({"a": 1, "b": 2}, {"b": 3, "c": 4})
	assert merged == {"a": 1, "b": 3, "c": 4}


def test_coerce_coords_handles_invalid_values():
	assert coerce_coords("45.5", "9.2") == (45.5, 9.2)
	assert coerce_coords(None, 9.2) == (None, None)
	assert coerce_coords("x", "y") == (None, None)


def test_normalize_notification_action_and_stationary_step_helpers():
	assert normalize_notification_action(" open_map ") == "OPEN_MAP"
	assert needs_stationary_step("position") is True
	assert needs_stationary_step("combined") is True
	assert needs_stationary_step("manual") is False


def test_should_save_after_stationary_within_tolerance():
	assert should_save_after_stationary(45.5, 9.2, 45.50001, 9.20001, 200) is True
	assert should_save_after_stationary(45.5, 9.2, 46.0, 10.0, 200) is False


def test_format_map_url():
	assert format_map_url(45.5, 9.2) == "https://maps.google.com/?q=45.5,9.2"

