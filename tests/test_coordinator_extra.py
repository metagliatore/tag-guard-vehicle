from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeStates:
	def get(self, entity_id):
		return None


class FakeHass:
	def __init__(self):
		self.states = FakeStates()


def test_validate_and_fix_state_sets_awaiting_when_active_without_position():
	coordinator = VehicleCoordinator(FakeHass(), "entry_1", {"activation_mode": "position"})
	coordinator.alarm_active = True
	coordinator._awaiting_activation_save = False
	coordinator.saved_latitude = None
	coordinator.saved_longitude = None

	coordinator._validate_and_fix_state()

	assert coordinator._awaiting_activation_save is True


def test_validate_and_fix_state_does_not_force_awaiting_for_connection_mode():
	coordinator = VehicleCoordinator(FakeHass(), "entry_1", {"activation_mode": "connection"})
	coordinator.alarm_active = True
	coordinator._awaiting_activation_save = False
	coordinator.saved_latitude = None
	coordinator.saved_longitude = None

	coordinator._validate_and_fix_state()

	assert coordinator._awaiting_activation_save is False

