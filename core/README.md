# edu_robot_api

A small, typed Python API for educational robotics. It represents robots,
sensors and actuators as Python objects and provides a consistent interface
for reading measurements and issuing movement commands.

RoboWorkbench uses the API for independent virtual learning robots. Their
behavior is defined by the learning environment. Available components,
measurements and motion depend on the selected model and world.

## Installation

Requires Python 3.11 or later. Install from PyPI with pip:

```sh
python -m pip install edu_robot_api
```

Alternatively, install a downloaded wheel:

```sh
python -m pip install edu_robot_api-0.6.0-py3-none-any.whl
```

In the RoboWorkbench web app, no local installation is needed.

## Documentation

See the [user guide and API overview](https://github.com/henningmattes/edu_robot_api#readme)
for examples and the class diagram. The
[source repository](https://github.com/henningmattes/edu_robot_api)
also provides the library source code.

## Programming in RoboWorkbench

The web app provides the connected robot for the current editor as `rob`.
Each robot program controls its own robot. The environment stops the robot
and releases the connection when the program finishes, fails or is aborted.

```python
import time


def program(robot):
    sensor = robot.sensors()["distance_front"]
    while True:
        distance = sensor.read()
        if distance is None or distance < 25:
            robot.stop()
        else:
            robot.forward(30)
        time.sleep(0.03)


program(rob)
```

This example requires a front distance sensor. In a standalone Python
application, the application must supply the robot object and its backend;
installing the API alone does not create a robot or a running simulation.

## Components and readings

`robot.sensors()` and `robot.actuators()` return dictionaries of component
objects. Use `sensor.read()` for an individual reading or
`robot.read_sensors()` for a snapshot. Snapshot values can be selected by
sensor object, captured name or position in the selection.

```python
left = rob.sensors()["line_left"]
right = rob.sensors()["line_right"]
values = rob.read_sensors([left, right])
print(values[left], values[right])
```

The package exports `Robot`, `Sensor`, `Actuator`, typed component classes,
`SensorReadings`, `Bridge`, `Backend` and `FunctionBackend`. Python applications
can implement the backend contract to provide measurements and execute commands.

Motor power is expressed as a percentage, distance in centimeters and angles
in degrees. Motor power is not a guaranteed speed. `None` indicates an unavailable
measurement; missing capabilities and connection failures can raise exceptions.

## License

The library is licensed under the Apache License, Version 2.0. See LICENSE.
