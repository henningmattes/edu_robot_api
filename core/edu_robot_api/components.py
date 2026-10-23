"""Portable component API (CPython and Pyodide). No transport dependencies."""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any, Generic, Protocol, TypeVar, overload

T = TypeVar("T")


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
    pass


class Motor(Actuator):
    pass


class DCMotor(Motor):
    def set_power(self, power: float) -> None:
        self._robot._set_motor(self, percent(power))

    def stop(self) -> None:
        self.set_power(0)


class ServoMotor(Motor):
    def __init__(self, *args: Any, minimum: float = 0, maximum: float = 180, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.minimum, self.maximum = minimum, maximum

    def set_angle(self, angle: float) -> None:
        if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not self.minimum <= angle <= self.maximum:
            raise ValueError(f"Servowinkel muss zwischen {self.minimum} und {self.maximum} Grad liegen.")
        self._robot._set_servo(self, angle)


class RGBLights(Actuator):
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
    def set_mode(self, mode: int) -> None:
        _mode(mode, 3)
        self._robot._call("matrix_mode", mode)


class Buzzer(Actuator):
    def set(self, enabled: bool = True, frequency: int = 2000) -> None:
        if not isinstance(enabled, bool) or isinstance(frequency, bool) or not isinstance(frequency, int) or not 20 <= frequency <= 20000:
            raise ValueError("Summer: bool und Frequenz 20 bis 20000 Hz erwartet.")
        self._robot._call("buzzer", enabled, frequency)

    def stop(self) -> None:
        self.set(False)


class Kicker(Actuator):
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
    def connect(name: str | None = None, *, bridge: Bridge | None = None,
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
        count = self._capabilities.get("motor_count", 2)
        wheel_names = ["motor_left", "motor_right"] if count == 2 else ["motor_front_left", "motor_rear_left", "motor_front_right", "motor_rear_right"]
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
                if identifier not in known or identifier in seen or not isinstance(label, str) or not label.strip():
                    raise ValueError("Ungültige Bauteilbeschreibung der Bridge.")
                seen.add(identifier)
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

    def _set_motor(self, motor: DCMotor, power: float) -> None:
        powers = self._powers.copy()
        powers[self._wheels.index(motor)] = power
        self.set_motors(*powers)

    def _set_servo(self, servo: ServoMotor, angle: float) -> None:
        angles = dict(self._angles)
        angles[servo._channel] = angle
        self._call("camera_orientation", angles["camera_pan"], angles["camera_tilt"])
        self._angles = angles

    def set_motors(self, *powers: float) -> None:
        if len(powers) != len(self._wheels):
            raise ValueError("Anzahl der Motorwerte passt nicht zum Modell.")
        values = [percent(p) for p in powers]
        self._call("set_motors", *values)
        self._powers = values

    def drive(self, linear: float, turn: float = 0) -> None:
        left, right = motor_pair(linear, turn)
        self.set_motors(*([left, right] if len(self._wheels) == 2 else [left, left, right, right]))

    def forward(self, power: float | None = None) -> None:
        self.drive(self._speed if power is None else percent(power))

    def backward(self, power: float | None = None) -> None:
        self.drive(-(self._speed if power is None else abs(percent(power))))

    def turn_left(self, power: float | None = None) -> None:
        self.drive(0, -(self._speed if power is None else abs(percent(power))))

    def turn_right(self, power: float | None = None) -> None:
        self.drive(0, self._speed if power is None else abs(percent(power)))

    def stop(self) -> None:
        self._call("stop")
        self._powers = [0.0] * len(self._wheels)

    def speed(self) -> float:
        return self._speed

    def set_speed(self, speed: float) -> None:
        self._speed = abs(percent(speed))

    def capabilities(self) -> dict[str, Any]:
        result = deepcopy(self._capabilities)
        result["sensors"] = list(self._sensors)
        result["actuators"] = list(self._actuators)
        result["commands"] = ["sensors", "actuators", "read_sensors", "rename", "drive", "set_motors",
                              "forward", "backward", "turn_left", "turn_right", "stop", "speed",
                              "set_speed", "time", "log", "disconnect", "close", "capabilities"]
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
            self.stop()
        finally:
            try:
                self._backend.call("close")
            finally:
                self._closed = True

    def close(self) -> None:
        """Compatibility alias for disconnect()."""
        self.disconnect()

    def __enter__(self) -> Robot:
        if self._closed:
            raise RuntimeError("Verbindung ist geschlossen.")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class Bridge:
    """Lifecycle of an explicitly selected robot endpoint. Factories do no I/O."""
    def __init__(self) -> None:
        self._started = False
        self._connection: Robot | None = None

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        self._started = False

    def _require_ready(self) -> None:
        if not self._started:
            raise RuntimeError("Zuerst bridge.start() aufrufen.")
        if self._connection is not None and not self._connection._closed:
            raise RuntimeError("Diese Bridge hat bereits eine Steuerverbindung.")

    def _connect(self, *, speed: float = 60) -> Robot:
        raise NotImplementedError


class WorkbenchBridge(Bridge):
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

    def _connect(self, *, speed: float = 60) -> Robot:
        self._require_ready()
        import edu_robot_api
        self._connection = edu_robot_api.connect_robot(self.robot_name, speed=speed)
        return self._connection
