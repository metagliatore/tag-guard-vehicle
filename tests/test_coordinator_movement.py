from custom_components.tag_guard_vehicle.coordinator import VehicleCoordinator


class FakeStates:
	def get(self, entity_id):
		return None


class FakeHass:
	def __init__(self):
		self.states = FakeStates()


def test_has_moved_returns_false_without_saved_position():
	coordinator = VehicleCoordinator(FakeHass(), "entry_1", {})
	assert coordinator.has_moved(45.0, 9.0, 100) is False


def test_has_moved_returns_true_when_beyond_tolerance():
	coordinator = VehicleCoordinator(FakeHass(), "entry_1", {})
	coordinator.saved_latitude = 45.0
	coordinator.saved_longitude = 9.0

	assert coordinator.has_moved(45.02, 9.0, 100) is True

