"""Portable component API (CPython and Pyodide). No transport dependencies."""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any, Generic, Protocol, TypeVar, Self, overload
from abc import ABC, abstractmethod

T = TypeVar("T")
RobotT = TypeVar("RobotT", bound="Robot")


class CapabilityUnavailable(Exception):
    """The connected robot does not provide this component or operation."""


class Backend(Protocol):
    def call(self, operation: str, *args: Any) -> Any: ...


class FunctionBackend:
    """Boundary adapter for existing device and simulator drivers."""
    def __init__(self, functions: Mapping[str, Callable[..., Any]]) -> None:
        self.functions = functions

    def call(self, operation: str, *args: Any) -> Any:
        if operation not in self.functions:
            raise CapabilityUnavailable(operation)
        try:
            return self.functions[operation](*args)
        except Exception as error:
            if type(error).__name__ == "CapabilityUnavailable":
                raise CapabilityUnavailable(str(error)) from error
            raise


def percent(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -float("inf") < value < float("inf"):
        raise ValueError("Motorleistung muss eine endliche Zahl sein.")
    return max(-100, min(100, value))


def motor_pair(linear: float, turn: float) -> tuple[float, float]:
    linear, turn = percent(linear), percent(turn)
    return percent(linear + turn), percent(linear - turn)


class Component:
    def __init__(self, robot: Robot, identifier: str, name: str, *, position: str | None = None) -> None:
        self._robot, self._channel, self._name = robot, identifier, name
        self._id = ("sensor:" if isinstance(self, Sensor) else "actuator:") + identifier
        self.position = position

    @property
    def id(self) -> str:
        """Stable within a connection, independent of the editable display name."""
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._robot.rename(self, value)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class Sensor(Component, Generic[T]):
    def read(self) -> T | None:
        return self._robot.read_sensors([self])[self]


class DistanceSensor(Sensor[float]):
    """Distance in centimetres; None means no usable measurement."""
    def obstacle_ahead(self, threshold_cm: float = 30) -> bool | None:
        if isinstance(threshold_cm, bool) or not isinstance(threshold_cm, (int, float)) or not 0 <= threshold_cm < float("inf"):
            raise ValueError("Abstand muss endlich und nicht negativ sein.")
        value = self.read()
        return None if value is None else value < threshold_cm


class LineSensor(Sensor[bool]):
    """Digital line detector: True means the dark line is detected."""


class ContactSensor(Sensor[bool]):
    pass


class Camera(Sensor[dict[str, Any]]):
    """RGB image: width, height, row-major pixels packed as 0xRRGGBB."""
    def read(self, *, full_resolution: bool = True) -> dict[str, Any] | None:
        return self._robot._call("camera_image" if full_resolution else "camera")

    def start(self) -> None:
        self._robot._call("start_camera")

    def stop(self) -> None:
        self._robot._call("stop_camera")


class SensorReadings(Mapping[Sensor[Any] | str | int, Any]):
    """A measurement snapshot. Iteration uses the names at capture time."""
    def __init__(self, sensors: Sequence[Sensor[Any]], values: Sequence[Any]) -> None:
        self._sensors = tuple(sensors)
        self._names = tuple(sensor.name for sensor in sensors)
        self._values = deepcopy(tuple(values))

    @overload
    def __getitem__(self, key: Sensor[T]) -> T | None: ...
    @overload
    def __getitem__(self, key: str | int) -> Any: ...
    def __getitem__(self, key: object) -> Any:
        if isinstance(key, bool):
            raise KeyError(key)
        if isinstance(key, int):
            return deepcopy(self._values[key])
        keys = self._names if isinstance(key, str) else self._sensors
        try:
            index = keys.index(key)
        except ValueError:
            raise KeyError(key) from None
        return deepcopy(self._values[index])

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._values)


class Actuator(Component):
    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        """Validate a value without I/O; subclasses may define new operations."""
        raise CapabilityUnavailable(type(self).__name__ + " has no scalar write operation")


class Motor(Actuator):
    pass


class DCMotor(Motor):
    def set_power(self, power: float) -> None:
        self._robot.write_actuators({self: power})

    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        return "motor", (percent(value),)

    def stop(self) -> None:
        self.set_power(0)


class ServoMotor(Motor):
    def __init__(self, *args: Any, minimum: float = 0, maximum: float = 180, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.minimum, self.maximum = minimum, maximum

    def set_angle(self, angle: float) -> None:
        self._robot.write_actuators({self: angle})

    def prepare_write(self, angle: Any) -> tuple[str, tuple[Any, ...]]:
        if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not self.minimum <= angle <= self.maximum:
            raise ValueError(f"Servowinkel muss zwischen {self.minimum} und {self.maximum} Grad liegen.")
        return "servo", (angle,)


class RGBLights(Actuator):
    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        if not isinstance(value, (tuple, list)) or len(value) != 3 or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255 for v in value):
            raise ValueError("Expected three RGB integers from 0 to 255.")
        return "rgb_led", (-1, *value)

    def set_color(self, index: int | str, red: int, green: int, blue: int) -> None:
        if index == "all":
            index = -1
        if isinstance(index, bool) or not isinstance(index, int) or not -1 <= index < self._robot._led_count:
            raise ValueError("Ungültiger LED-Index.")
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255 for v in (red, green, blue)):
            raise ValueError("RGB-Werte müssen ganze Zahlen von 0 bis 255 sein.")
        self._robot._call("rgb_led", index, red, green, blue)

    def set_mode(self, mode: int) -> None:
        _mode(mode, 5)
        self._robot._call("rgb_mode", mode)


def _mode(value: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"Modus muss eine ganze Zahl von 0 bis {maximum} sein.")


class LEDMatrix(Actuator):
    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        _mode(value, 3)
        return "matrix_mode", (value,)

    def set_mode(self, mode: int) -> None:
        _mode(mode, 3)
        self._robot._call("matrix_mode", mode)


class Buzzer(Actuator):
    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("Expected (enabled, frequency).")
        enabled, frequency = value
        if not isinstance(enabled, bool) or isinstance(frequency, bool) or not isinstance(frequency, int) or not 20 <= frequency <= 20000:
            raise ValueError("Expected bool and frequency between 20 and 20000 Hz.")
        return "buzzer", (enabled, frequency)

    def set(self, enabled: bool = True, frequency: int = 2000) -> None:
        if not isinstance(enabled, bool) or isinstance(frequency, bool) or not isinstance(frequency, int) or not 20 <= frequency <= 20000:
            raise ValueError("Summer: bool und Frequenz 20 bis 20000 Hz erwartet.")
        self._robot._call("buzzer", enabled, frequency)

    def stop(self) -> None:
        self.set(False)


class Kicker(Actuator):
    def prepare_write(self, value: Any) -> tuple[str, tuple[Any, ...]]:
        return "kick", (max(0, percent(value)),)

    def kick(self, power: float = 75) -> None:
        self._robot._call("kick", max(0, percent(power)))


class SimulationView:
    """Optional observations; never advertised by a physical bridge."""
    def __init__(self, robot: Robot) -> None:
        self._robot = robot

    def position(self) -> dict[str, float]:
        return self._robot._call("position")

    def ball_position(self) -> dict[str, float]:
        return self._robot._call("ball_position")

    def opponent_position(self) -> dict[str, float] | None:
        return self._robot._call("opponent_position")

    def goal_position(self) -> dict[str, float]:
        return self._robot._call("goal_position")

    def ball_distance(self) -> float:
        return self._robot._call("ball_distance")

    def ball_angle(self) -> float:
        return self._robot._call("ball_angle")

    def kickoff_wait(self) -> bool:
        return self._robot._call("kickoff_wait")

    def kickoff_time(self) -> float:
        return self._robot._call("kickoff_time")


class Robot:
    """One named connection, composed of components; operations delegate to a backend."""
    @staticmethod
    @overload
    def connect(*, bridge: Bridge[RobotT], speed: float = 60) -> RobotT: ...

    @staticmethod
    @overload
    def connect(name: str | None = None, *, speed: float = 60, **options: Any) -> Robot: ...

    @staticmethod
    def connect(name: str | None = None, *, bridge: Bridge[Any] | None = None,
                speed: float = 60, **options: Any) -> Robot:
        """Create a connected robot; release it with disconnect()."""
        if bridge is not None:
            if name is not None or options:
                raise ValueError("Bei bridge= nur die Bridge und optional speed angeben.")
            return bridge._connect(speed=speed)
        from edu_robot_api import connect_robot
        return connect_robot(name, speed=speed, **options)

    def __init__(self, backend: Backend, *, name: str, model: str, speed: float = 60,
                 components: Sequence[Mapping[str, Any]] | None = None) -> None:
        self._backend, self.name, self.model = backend, name, model
        self.id = name
        self.memory: dict[str, Any] = {}
        self._closed = False
        self._speed = abs(percent(speed))
        self._capabilities = backend.call("capabilities")
        self.simulation = SimulationView(self)
        self._sensors: dict[str, Sensor[Any]] = {}
        self._actuators: dict[str, Actuator] = {}
        for key in self._capabilities["sensors"]:
            cls: type[Sensor[Any]] = DistanceSensor if key.startswith("distance_") else LineSensor if key.startswith("line_") and key != "line_raw" else ContactSensor if key.startswith("bumper_") else Sensor
            self._sensors[key] = cls(self, key, key, position=key.split("_", 1)[1] if "_" in key else None)
        count = self._capabilities.get("motor_count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("motor_count must be a non-negative integer")
        wheel_names = ["motor_left", "motor_right"] if count == 2 else ["motor_front_left", "motor_rear_left", "motor_front_right", "motor_rear_right"] if count == 4 else [f"motor_{i}" for i in range(count)]
        self._wheels = [DCMotor(self, key, key, position=key.removeprefix("motor_")) for key in wheel_names]
        self._powers = [0.0] * count
        self._angles = {"camera_pan": 90.0, "camera_tilt": 90.0}
        self._led_count = 4 if count == 2 else 12
        self._actuators.update((motor.name, motor) for motor in self._wheels)
        commands = self._capabilities["commands"]
        if "camera" in commands:
            self._sensors["camera"] = Camera(self, "camera", "camera", position="front")
        for command, key, actuator_cls in [("rgb_led", "rgb_leds", RGBLights), ("buzzer", "buzzer", Buzzer), ("matrix_mode", "matrix", LEDMatrix), ("kick", "kicker", Kicker)]:
            if command in commands:
                self._actuators[key] = actuator_cls(self, key, key)
        if "camera_orientation" in commands:
            for key in self._angles:
                self._actuators[key] = ServoMotor(self, key, key, minimum=80 if key == "camera_tilt" else 0)
        if components is not None:
            known = {component.id: component for component in [*self._sensors.values(), *self._actuators.values()]}
            sensors: dict[str, Sensor[Any]] = {}
            actuators: dict[str, Actuator] = {}
            seen: set[str] = set()
            for spec in components:
                identifier, label = spec.get("id"), spec.get("name")
                if not isinstance(identifier, str) or identifier in seen or not isinstance(label, str) or not label.strip():
                    raise ValueError("Ungültige Bauteilbeschreibung der Bridge.")
                seen.add(identifier)
                if identifier not in known:
                    kind, separator, channel = identifier.partition(":")
                    types = {c.__name__: c for c in (Sensor, DistanceSensor, LineSensor, ContactSensor, Camera,
                                                     DCMotor, ServoMotor, RGBLights, LEDMatrix, Buzzer, Kicker)}
                    component_type: Any = types.get(str(spec.get("type")))
                    if not separator or not channel or component_type is None or (kind == "sensor") != issubclass(component_type, Sensor) or kind not in ("sensor", "actuator"):
                        raise ValueError("Invalid component type or identifier: " + identifier)
                    options = {k: spec[k] for k in ("minimum", "maximum") if k in spec} if component_type is ServoMotor else {}
                    known[identifier] = component_type(self, channel, label, position=spec.get("position"), **options)
                component = known[identifier]
                if spec.get("type") != type(component).__name__:
                    raise ValueError("Bauteiltyp passt nicht zum Modell: " + identifier)
                registry: dict[str, Any] = sensors if isinstance(component, Sensor) else actuators
                if label in registry:
                    raise ValueError("Doppelter Bauteilname: " + label)
                component._name, component.position = label, spec.get("position")
                registry[label] = component
            if any(wheel.id not in seen for wheel in self._wheels):
                raise ValueError("Die Beschreibung enthält nicht alle Antriebsmotoren.")
            self._sensors, self._actuators = sensors, actuators
        self._wheels = [a for a in self._actuators.values() if isinstance(a, DCMotor)]
        self._powers = [0.0] * len(self._wheels)
        self._angles.update({a._channel: 90.0 for a in self._actuators.values() if isinstance(a, ServoMotor)})

    def _call(self, operation: str, *args: Any) -> Any:
        if self._closed:
            raise RuntimeError("Verbindung ist geschlossen.")
        return self._backend.call(operation, *args)

    def sensors(self) -> dict[str, Sensor[Any]]:
        return dict(self._sensors)

    def actuators(self) -> dict[str, Actuator]:
        return dict(self._actuators)

    def rename(self, component: Component, name: str) -> None:
        registry: dict[str, Any] = self._sensors if isinstance(component, Sensor) else self._actuators
        if component._robot is not self or registry.get(component.name) is not component:
            raise ValueError("Bauteil gehört nicht zu diesem Roboter.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Bauteilname darf nicht leer sein.")
        if name in registry and registry[name] is not component:
            raise ValueError("Bauteilname ist bereits vergeben: " + name)
        # Rebuild in place to preserve mounting/selection order.
        entries = [(name if value is component else key, value) for key, value in registry.items()]
        registry.clear()
        registry.update(entries)
        component._name = name

    def read_sensors(self, selection: Sequence[Sensor[Any] | str] | None = None) -> SensorReadings:
        if isinstance(selection, (str, bytes)):
            raise TypeError("Sensoren als Liste übergeben, zum Beispiel ['line_left'].")
        selected = list(self._sensors.values()) if selection is None else [self._sensors[s] if isinstance(s, str) else s for s in selection]
        if any(not isinstance(s, Sensor) or s._robot is not self or self._sensors.get(s.name) is not s for s in selected):
            raise ValueError("Sensor gehört nicht zu diesem Roboter.")
        if len(set(selected)) != len(selected):
            raise ValueError("Sensor wurde mehrfach angefordert.")
        if not selected:
            return SensorReadings([], [])
        # One telemetry refresh for all requested non-camera values. Never call read() in a loop.
        values = self._call("update_sensors") if any(not isinstance(s, Camera) for s in selected) else {}
        return SensorReadings(selected, [self._call("camera_image") if isinstance(s, Camera) else values.get(s._channel) for s in selected])

    def register_sensor(self, name: str, sensor: Sensor[Any]) -> None:
        self._register(name, sensor, self._sensors, Sensor)

    def register_actuator(self, name: str, actuator: Actuator) -> None:
        self._register(name, actuator, self._actuators, Actuator)
        if isinstance(actuator, DCMotor) and actuator not in self._wheels:
            self._wheels.append(actuator)
            self._powers.append(0.0)

    def _register(self, name: str, component: Component, registry: dict, expected: type) -> None:
        if self._closed:
            raise RuntimeError("Verbindung ist geschlossen.")
        if not isinstance(component, expected) or component._robot is not self:
            raise ValueError("Component belongs to another robot or collection.")
        if not isinstance(name, str) or not name.strip() or name in registry or any(c.id == component.id for c in registry.values()):
            raise ValueError("Invalid or duplicate component name/identifier.")
        component._name = name
        registry[name] = component

    def write_actuators(self, values: Mapping[Actuator | str, Any]) -> None:
        """Validate the whole request before I/O. Batch-capable backends receive one request.

        Legacy backends group wheel powers and camera servos; other groups execute
        in order, without a claim of hardware-level atomicity or rollback.
        """
        if self._closed:
            raise RuntimeError("Verbindung ist geschlossen.")
        if not isinstance(values, Mapping):
            raise TypeError("Actuator values must be a mapping.")
        prepared = []
        seen = set()
        for key, value in values.items():
            actuator = self._actuators[key] if isinstance(key, str) else key
            if not isinstance(actuator, Actuator) or actuator._robot is not self or self._actuators.get(actuator.name) is not actuator or actuator.id in seen:
                raise ValueError("Unknown, foreign or duplicate actuator.")
            seen.add(actuator.id)
            operation, args = actuator.prepare_write(value)
            prepared.append((actuator, operation, args))
        if not prepared:
            return
        powers, angles = self._powers.copy(), dict(self._angles)
        for actuator, operation, args in prepared:
            if operation == "motor":
                if not isinstance(actuator, DCMotor):
                    raise ValueError("Motor operation requires a DCMotor")
                powers[self._wheels.index(actuator)] = args[0]
            elif operation == "servo":
                angles[actuator._channel] = args[0]
        if "write_actuators" in self._capabilities.get("commands", []):
            self._call("write_actuators", [dict(id=a.id, operation=op, args=list(args)) for a, op, args in prepared])
            self._powers, self._angles = powers, angles
            return
        # Check unsupported servos before issuing any command.
        if any(op == "servo" and a._channel not in ("camera_pan", "camera_tilt") for a, op, _ in prepared):
            raise CapabilityUnavailable("This backend needs write_actuators for arbitrary servos.")
        commands = []
        motor_group = servo_group = False
        for actuator, operation, args in prepared:
            if operation == "motor":
                if not motor_group:
                    commands.append(("set_motors", tuple(powers)))
                    motor_group = True
            elif operation == "servo":
                if not servo_group:
                    commands.append(("camera_orientation", (angles["camera_pan"], angles["camera_tilt"])))
                    servo_group = True
            else:
                commands.append((operation, args))
        for operation, args in commands:
            self._call(operation, *args)
            if operation == "set_motors":
                self._powers = powers
            elif operation == "camera_orientation":
                self._angles = angles

    def capabilities(self) -> dict[str, Any]:
        result = deepcopy(self._capabilities)
        result["sensors"] = list(self._sensors)
        result["actuators"] = list(self._actuators)
        result["commands"] = ["sensors", "actuators", "read_sensors", "write_actuators", "rename",
                              "time", "log", "disconnect", "close", "capabilities"]
        for command in ("drive", "forward", "backward", "turn_left", "turn_right", "stop",
                        "set_motors", "speed", "set_speed", "fly", "takeoff", "land"):
            if callable(getattr(self, command, None)):
                result["commands"].append(command)
        return result

    def time(self) -> float:
        return self._call("time")

    def log(self, message: object) -> None:
        self._call("log", str(message))

    def disconnect(self) -> None:
        """Stop motors and release this control connection; idempotent."""
        if self._closed:
            return
        try:
            self._shutdown()
        finally:
            try:
                self._backend.call("close")
            finally:
                self._closed = True

    def _shutdown(self) -> None:
        # A backend owns its device-specific safe release policy.
        self._call("stop")
        self._powers = [0.0] * len(self._wheels)

    def close(self) -> None:
        """Compatibility alias for disconnect()."""
        self.disconnect()

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("Verbindung ist geschlossen.")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class DifferentialDrive(Actuator):
    """One drive, referencing existing motors and an injected bound batch writer."""
    def __init__(self, robot: Robot, left_motors: Sequence[DCMotor], right_motors: Sequence[DCMotor],
                 write_actuators: Callable[[Mapping[Actuator | str, Any]], None], *, speed: float = 60) -> None:
        super().__init__(robot, "drive", "drive")
        motors = (*left_motors, *right_motors)
        if not left_motors or not right_motors or len(set(motors)) != len(motors):
            raise ValueError("Drive sides must be non-empty and disjoint.")
        if any(not isinstance(m, DCMotor) or m._robot is not robot or robot.actuators().get(m.name) is not m for m in motors):
            raise ValueError("Drive motors must be registered on this robot.")
        self.__left, self.__right = tuple(left_motors), tuple(right_motors)
        self.__write = write_actuators
        self.set_speed(speed)

    def drive(self, linear: float, turn: float = 0) -> None:
        left, right = motor_pair(linear, turn)
        self.__write({**{m: left for m in self.__left}, **{m: right for m in self.__right}})

    def forward(self, power: float | None = None) -> None:
        self.drive(self.__speed if power is None else percent(power))

    def backward(self, power: float | None = None) -> None:
        self.drive(-(self.__speed if power is None else abs(percent(power))))

    def turn_left(self, power: float | None = None) -> None:
        self.drive(0, -(self.__speed if power is None else abs(percent(power))))

    def turn_right(self, power: float | None = None) -> None:
        self.drive(0, self.__speed if power is None else abs(percent(power)))

    def stop(self) -> None:
        self.drive(0, 0)

    def speed(self) -> float:
        return self.__speed

    def set_speed(self, speed: float) -> None:
        self.__speed = abs(percent(speed))


class HasDifferentialDrive(ABC):
    @property
    @abstractmethod
    def differential_drive(self) -> DifferentialDrive: ...

    def forward(self, power: float | None = None) -> None:
        self.differential_drive.forward(power)

    def backward(self, power: float | None = None) -> None:
        self.differential_drive.backward(power)

    def turn_left(self, power: float | None = None) -> None:
        self.differential_drive.turn_left(power)

    def turn_right(self, power: float | None = None) -> None:
        self.differential_drive.turn_right(power)

    def drive(self, linear: float, turn: float = 0) -> None:
        self.differential_drive.drive(linear, turn)

    def stop(self) -> None:
        self.differential_drive.stop()

    def speed(self) -> float:
        return self.differential_drive.speed()

    def set_speed(self, speed: float) -> None:
        self.differential_drive.set_speed(speed)


class WheeledRobot(Robot, HasDifferentialDrive):
    """Neutral model for simulated or physical wheels; no vendor dependency."""
    def __init__(self, *args: Any, left_motors: Sequence[str] | None = None,
                 right_motors: Sequence[str] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        by_channel = {m._channel: m for m in self._wheels}
        if left_motors is None and right_motors is None:
            left_motors = [m._channel for m in self._wheels if "left" in (m.position or m._channel)]
            right_motors = [m._channel for m in self._wheels if "right" in (m.position or m._channel)]
        if left_motors is None or right_motors is None:
            raise ValueError("Specify both drive sides.")
        self.__drive = DifferentialDrive(self, [by_channel[k] for k in left_motors],
                                        [by_channel[k] for k in right_motors], self.write_actuators,
                                        speed=self._speed)
        self.register_actuator("drive", self.__drive)

    @property
    def differential_drive(self) -> DifferentialDrive:
        return self.__drive

    def set_motors(self, *powers: float) -> None:
        """Compatibility shortcut; new programs can use write_actuators."""
        if len(powers) != len(self._wheels):
            raise ValueError("Anzahl der Motorwerte passt nicht zum Modell.")
        self.write_actuators(dict(zip(self._wheels, powers)))


class FlightController(Actuator):
    """Normalized motion commands, not rotor power or guaranteed velocity."""
    def __init__(self, robot: Robot, *, speed: float = 30) -> None:
        super().__init__(robot, "flight", "flight")
        self.set_speed(speed)

    def takeoff(self) -> None:
        self._robot._call("takeoff")

    def land(self) -> None:
        self._robot._call("land")

    def fly(self, forward: float = 0, right: float = 0, up: float = 0, yaw: float = 0) -> None:
        self._robot._call("flight_control", *(percent(v) for v in (forward, right, up, yaw)))

    def forward(self, power: float | None = None) -> None:
        self.fly(forward=self.__speed if power is None else power)

    def backward(self, power: float | None = None) -> None:
        self.fly(forward=-(self.__speed if power is None else abs(percent(power))))

    def turn_left(self, power: float | None = None) -> None:
        self.fly(yaw=-(self.__speed if power is None else abs(percent(power))))

    def turn_right(self, power: float | None = None) -> None:
        self.fly(yaw=self.__speed if power is None else abs(percent(power)))

    def hover(self) -> None:
        self._robot._call("hover")

    def stop(self) -> None:
        self.hover()

    def speed(self) -> float:
        return self.__speed

    def set_speed(self, speed: float) -> None:
        self.__speed = abs(percent(speed))


class HasFlightController(ABC):
    @property
    @abstractmethod
    def flight_controller(self) -> FlightController: ...

    def takeoff(self) -> None:
        self.flight_controller.takeoff()

    def land(self) -> None:
        self.flight_controller.land()

    def fly(self, forward: float = 0, right: float = 0, up: float = 0, yaw: float = 0) -> None:
        self.flight_controller.fly(forward, right, up, yaw)

    def forward(self, power: float | None = None) -> None:
        self.flight_controller.forward(power)

    def backward(self, power: float | None = None) -> None:
        self.flight_controller.backward(power)

    def turn_left(self, power: float | None = None) -> None:
        self.flight_controller.turn_left(power)

    def turn_right(self, power: float | None = None) -> None:
        self.flight_controller.turn_right(power)

    def stop(self) -> None:
        self.flight_controller.stop()

    def speed(self) -> float:
        return self.flight_controller.speed()

    def set_speed(self, speed: float) -> None:
        self.flight_controller.set_speed(speed)


class FlyingRobot(Robot, HasFlightController):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.__flight = FlightController(self, speed=self._speed)
        self.register_actuator("flight", self.__flight)

    @property
    def flight_controller(self) -> FlightController:
        return self.__flight


class Bridge(Generic[RobotT]):
    """Lifecycle of an explicitly selected robot endpoint. Factories do no I/O."""
    def __init__(self) -> None:
        self._started = False
        self._connection: RobotT | None = None

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        self._started = False

    def _require_ready(self) -> None:
        if not self._started:
            raise RuntimeError("Zuerst bridge.start() aufrufen.")
        if self._connection is not None and not self._connection._closed:
            raise RuntimeError("Diese Bridge hat bereits eine Steuerverbindung.")

    def _connect(self, *, speed: float = 60) -> RobotT:
        raise NotImplementedError


class WorkbenchBridge(Bridge[WheeledRobot]):
    """Select a robot in the current Workbench world; no native process."""
    robot_name: str
    @classmethod
    def create(cls, *, robot_name: str) -> WorkbenchBridge:
        if not isinstance(robot_name, str) or not robot_name.strip():
            raise ValueError("Ein Robotername aus dem Welteditor ist erforderlich.")
        instance = cls()
        instance.robot_name = robot_name
        return instance

    def start(self) -> None:
        import edu_robot_api
        prepare = getattr(edu_robot_api, "_prepare_workbench_bridge", None)
        if prepare is None:
            raise RuntimeError("WorkbenchBridge ist nur in RoboWorkbench verfügbar.")
        prepare(self.robot_name)
        self._started = True

    def _connect(self, *, speed: float = 60) -> WheeledRobot:
        self._require_ready()
        import edu_robot_api
        self._connection = edu_robot_api.connect_robot(self.robot_name, speed=speed)
        return self._connection
