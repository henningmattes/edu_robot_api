# edu_robot_api

A typed Python API for educational robotics, built from sensors, actuators and
optional movement capabilities. RoboWorkbench uses it for independent virtual
learning robots whose behavior is defined by the selected model and world.

## Installation

Requires Python 3.11 or later. The latest published version is available on PyPI:

```sh
python -m pip install edu_robot_api
```

Alternatively, install a downloaded wheel:

```sh
python -m pip install ./edu_robot_api-0.7.0-py3-none-any.whl
```

Installing the API does not create a robot or start a simulation. A standalone
application supplies the robot's backend and connection. The RoboWorkbench web
app already includes its Python runtime and provides its connected robot as `rob`.

## Programming in RoboWorkbench

Each robot editor has its own `rob` and independent Python program. The following
example needs a wheeled robot with a front distance sensor:

```python
import time

def program(robot):
    front = robot.sensors()["distance_front"]
    while True:
        distance = front.read()
        if distance is None or distance < 25:
            robot.stop()
        else:
            robot.forward(30)
        time.sleep(0.03)

program(rob)
```

The web app stops and releases the robot when its program ends, fails, is stopped
or reset. No connection calls or `try/finally` are needed in these web programs.
Two editors run concurrently; sleeping in one program does not block the other.
A program cannot take over another editor's robot.

## Base class and movement capabilities

`Robot` manages components, snapshots, batch writes and the connection lifecycle.
It does not define `forward`, `drive` or `stop`. A `WheeledRobot` combines `Robot`
with `HasDifferentialDrive`. Its read-only `differential_drive` property returns
the same `DifferentialDrive` object as `robot.actuators()["drive"]`.

The capability class implements the convenience methods by delegating to that
component. The component holds the existing left and right motor objects and
the bound `robot.write_actuators` method. It supports any non-empty number of
motors on each side, with no two-versus-four-motor branch in its movement logic.

```python
from edu_robot_api import HasDifferentialDrive

if isinstance(rob, HasDifferentialDrive):
    rob.drive(30, 10)
    # Equivalent: rob.differential_drive.drive(30, 10)
```

This check is optional when the program already knows its robot's capabilities.
Type annotations are optional too. `HasDifferentialDrive` is an abstract class
with an abstract property; a subclass must supply it before it can be instantiated.

`FlyingRobot` similarly combines `Robot` with `HasFlightController` and a
`FlightController`. It provides `takeoff`, `fly`, `land` and directional commands.
Its `stop()` requests hovering, not rotor shutdown. It has no differential drive
or fictitious wheel motors. Flight controls are normalized commands, not raw
rotor power or guaranteed velocities. The backend defines execution and timeouts.

## Sensors and actuators

The base class alone is sufficient to access every registered component:

```python
left_sensor = rob.sensors()["line_left"]
values = rob.read_sensors([left_sensor, "line_right"])
print(values[left_sensor], values["line_right"])

left_motor = rob.actuators()["motor_left"]
right_motor = rob.actuators()["motor_right"]
rob.write_actuators({left_motor: -30, right_motor: 30})
```

`read_sensors` captures one telemetry snapshot plus requested camera data.
Results can be accessed by sensor object, captured name or selection index.
Camera and telemetry acquisition are not guaranteed to occur at the same instant.
`None` means no usable reading; connection failures may raise exceptions.

`write_actuators` validates the complete request before issuing commands. A backend
can accept one batch. With older backends, motor values are sent together and
camera servo values are sent together; different operation groups are sequential.
This is not a transaction or a guarantee of simultaneous physical action. A
transport failure can leave an earlier group applied. Do not retry blindly.

Names can change without changing component identity. Registered components must
belong to that robot. `register_sensor` and `register_actuator` let application
classes add components; the backend must implement their operations.

Built-in sensor types are `Sensor`, `DistanceSensor`, `LineSensor`, `ContactSensor`
and `Camera`. Actuator types include `DCMotor`, `ServoMotor`, `RGBLights`,
`LEDMatrix`, `Buzzer` and `Kicker`. These classes do not imply every robot has them.

Distances use centimeters, angles use degrees and motor commands use percentages
from -100 to 100. Motor power is not a guaranteed speed. For a differential drive,
positive `turn` steers right. Model, environment and timing affect results.

## Connections and typing

`Robot.connect(bridge=bridge)` delegates construction to a `Bridge[T]` and returns
that concrete robot type `T`. Python type checkers can retain this type; callers
do not need a cast. `disconnect()` applies the backend's release policy and closes
the connection even if stopping fails. It is idempotent after cleanup.

`Backend` is a Python `Protocol` requiring `call(operation, *args)`.
`FunctionBackend` implements it structurally using a dictionary of functions.
The package includes type annotations and `py.typed`.

## Class overview

![API class diagram](https://raw.githubusercontent.com/henningmattes/edu_robot_api/main/docs/images/components.svg)

Solid hollow triangles denote inheritance. A dashed hollow triangle denotes
structural protocol implementation. Labeled arrows identify references and
delegation; dashed arrows with an open arrowhead indicate use or construction.

## Migration from 0.6

Programs using the web app's `rob` or a wheeled connection factory retain their
movement calls. Code constructing `Robot(...)` directly for wheel motion should
construct `WheeledRobot(...)` instead, or use its atomic motor objects explicitly.
`set_motors` remains a compatibility shortcut on `WheeledRobot`.

## Documentation and source

See the [public GitHub repository](https://github.com/henningmattes/edu_robot_api)
and its [user guide](https://github.com/henningmattes/edu_robot_api#readme).
The repository contains the source in `core/`, installation wheels in `wheels/`
and file checksums in `SHA256.json`.

## License

Apache License, Version 2.0. See LICENSE in the package source.
