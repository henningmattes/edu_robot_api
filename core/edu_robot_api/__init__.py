"""Typed robot, sensor and actuator interfaces for educational programs."""
# Resolve package modules across Python search-path entries.
from pkgutil import extend_path as _extend_path

__path__ = _extend_path(__path__, __name__)
del _extend_path

from .components import (Actuator, Backend, Buzzer, Camera, CapabilityUnavailable,
                         Component, ContactSensor, DCMotor, DistanceSensor,
                         FunctionBackend, Kicker, LEDMatrix, LineSensor, Motor,
                         RGBLights, Robot, Sensor, SensorReadings, ServoMotor,
                         motor_pair, percent)
from .components import Bridge, WorkbenchBridge
from .connection import connect_robot

__version__ = "0.7.0"
__all__ = ["Robot", "connect_robot", "Bridge", "WorkbenchBridge", "Sensor", "DistanceSensor", "LineSensor",
           "ContactSensor", "Camera", "SensorReadings", "Component", "Actuator", "Motor", "DCMotor",
           "ServoMotor", "RGBLights", "LEDMatrix", "Buzzer", "Kicker", "Backend", "FunctionBackend",
           "CapabilityUnavailable", "motor_pair", "percent"]

from .components import (DifferentialDrive, HasDifferentialDrive, WheeledRobot,
                         FlightController, HasFlightController, FlyingRobot)
__all__ += ["DifferentialDrive", "HasDifferentialDrive", "WheeledRobot",
            "FlightController", "HasFlightController", "FlyingRobot"]
