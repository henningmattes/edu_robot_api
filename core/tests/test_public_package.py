"""Tests the public API with a local in-memory backend."""
import sys
import unittest
from edu_robot_api import Bridge, FunctionBackend, Robot


class LocalBridge(Bridge):
    def __init__(self):
        self.calls = []

    def _connect(self, *, speed=60):
        return Robot(FunctionBackend({
            "capabilities": lambda: {"sensors": ["line_left", "line_right"], "motor_count": 2, "commands": []},
            "update_sensors": lambda: {"line_left": True, "line_right": False},
            "stop": lambda: self.calls.append("stop"),
            "close": lambda: self.calls.append("disconnect"),
        }), name="Demo", model="generic", speed=speed)


class PublicPackageTest(unittest.TestCase):
    def test_connection_and_sensor_snapshot(self):
        bridge = LocalBridge()
        robot = Robot.connect(bridge=bridge)
        try:
            left = robot.sensors()["line_left"]
            values = robot.read_sensors([left, "line_right"])
            self.assertIs(values[left], True)
            self.assertIs(values["line_left"], True)
            self.assertIs(values[0], True)
            self.assertIs(values[1], False)
        finally:
            robot.disconnect()
        self.assertIn("disconnect", bridge.calls)


if __name__ == "__main__":
    unittest.main()
