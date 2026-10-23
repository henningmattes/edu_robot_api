"""Portable Python API. This same source is also executed by RoboWorkbench.

The backend is a dictionary of callables; no transport, device or browser globals
are exposed to learning programs. Distances are cm, angles degrees, motor power %.
"""


from edu_robot_api.components import CapabilityUnavailable


def percent(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Motorleistung muss eine endliche Zahl sein.")
    if value != value or abs(value) == float("inf"):
        raise ValueError("Motorleistung muss eine endliche Zahl sein.")
    return max(-100, min(100, value))


def motor_pair(linear, turn):
    """Positive turn turns right: the left wheels run faster than the right."""
    linear, turn = percent(linear), percent(turn)
    return percent(linear + turn), percent(linear - turn)


class Robot:
    def __init__(self, backend, name="Robot", model="simulation", speed=60):
        self._backend = backend
        self.id = name
        self.model = model
        self.memory = {}
        self._speed = abs(percent(speed))

    def capabilities(self):
        return self._backend["capabilities"]()

    def has_sensor(self, name):
        return name in self.capabilities()["sensors"]

    def supports(self, name):
        capabilities = self.capabilities()
        return name in capabilities["commands"] or name in capabilities["sensors"]

    def _require(self, name):
        if not self.supports(name):
            raise CapabilityUnavailable("Fähigkeit nicht verfügbar: " + name)

    def drive(self, linear, turn=0):
        return self._backend["drive"](percent(linear), percent(turn))

    def forward(self, speed=None):
        return self.drive(self._speed if speed is None else speed, 0)

    def backward(self, speed=None):
        return self.drive(-abs(self._speed if speed is None else percent(speed)), 0)

    def turn_left(self, speed=None):
        return self.drive(0, -abs(self._speed if speed is None else percent(speed)))

    def turn_right(self, speed=None):
        return self.drive(0, abs(self._speed if speed is None else percent(speed)))

    def stop(self):
        return self._backend["stop"]()

    def set_motors(self, *values):
        """Individual motor outputs in percent, in the model's motor order."""
        self._require("set_motors")
        if len(values) != self.capabilities()["motor_count"]:
            raise ValueError("Anzahl der Motorwerte passt nicht zum Modell.")
        return self._backend["set_motors"](*(percent(value) for value in values))

    def speed(self):
        return self._speed

    def set_speed(self, speed):
        self._speed = abs(percent(speed))

    def update_sensors(self):
        """Refresh once, then read a consistent snapshot using read_sensor()."""
        return self._backend["update_sensors"]()

    def sensors(self):
        return self._backend["sensors"]()

    def read_sensor(self, name):
        if not self.has_sensor(name):
            raise CapabilityUnavailable("Sensor nicht verfügbar: " + name)
        return self.sensors().get(name)

    def distance_front(self):
        return self.read_sensor("distance_front")

    def distance_left(self):
        return self.read_sensor("distance_left")

    def distance_right(self):
        return self.read_sensor("distance_right")

    def line_left(self):
        return self.read_sensor("line_left")

    def line_right(self):
        return self.read_sensor("line_right")

    def bumper_left(self):
        return self.read_sensor("bumper_left")

    def bumper_right(self):
        return self.read_sensor("bumper_right")

    def obstacle_ahead(self, threshold_cm=30):
        if isinstance(threshold_cm, bool) or not isinstance(threshold_cm, (int, float)) or not 0 <= threshold_cm < float("inf"):
            raise ValueError("Abstand muss eine endliche, nicht negative Zahl sein.")
        value = self.distance_front()
        return None if value is None else value < threshold_cm

    def set_rgb(self, index, red, green, blue):
        self._require("rgb_led")
        for value in (red, green, blue):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError("RGB-Werte müssen ganze Zahlen von 0 bis 255 sein.")
        return self._backend["rgb_led"](index, red, green, blue)

    def camera_frame(self):
        self._require("camera")
        return self._backend["camera"]()

    def camera_image(self):
        """Full-resolution image, using the same portable RGB format as camera_frame."""
        self._require("camera_image")
        return self._backend["camera_image"]()

    def start_camera(self):
        self._require("start_camera")
        return self._backend["start_camera"]()

    def stop_camera(self):
        self._require("stop_camera")
        return self._backend["stop_camera"]()

    def set_rgb_mode(self, mode):
        self._require("rgb_mode")
        if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 5:
            raise ValueError("LED-Modus muss eine ganze Zahl von 0 bis 5 sein.")
        return self._backend["rgb_mode"](mode)

    def set_matrix_mode(self, mode):
        self._require("matrix_mode")
        if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 3:
            raise ValueError("Matrix-Modus muss eine ganze Zahl von 0 bis 3 sein.")
        return self._backend["matrix_mode"](mode)

    def set_camera_orientation(self, pan, tilt):
        self._require("camera_orientation")
        for value in (pan, tilt):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 180:
                raise ValueError("Servowinkel muss zwischen 0 und 180 Grad liegen.")
        return self._backend["camera_orientation"](pan, tilt)

    def buzzer(self, enabled=True, frequency=2000):
        self._require("buzzer")
        if not isinstance(enabled, bool) or isinstance(frequency, bool) or not isinstance(frequency, int) or not 20 <= frequency <= 20000:
            raise ValueError("Summer: bool und Frequenz von 20 bis 20000 Hz erwartet.")
        return self._backend["buzzer"](enabled, frequency)

    def time(self):
        return self._backend["time"]()

    def log(self, message):
        return self._backend["log"](str(message))

    def close(self):
        try:
            self.stop()
        finally:
            self._backend["close"]()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    # Explicit simulation capabilities: these are never claimed by real hardware.
    def position(self):
        self._require("position")
        return self._backend["position"]()

    def ball_position(self):
        self._require("ball_position")
        return self._backend["ball_position"]()

    def opponent_position(self):
        self._require("opponent_position")
        return self._backend["opponent_position"]()

    def goal_position(self):
        self._require("goal_position")
        return self._backend["goal_position"]()

    def ball_distance(self):
        self._require("ball_distance")
        return self._backend["ball_distance"]()

    def ball_angle(self):
        self._require("ball_angle")
        return self._backend["ball_angle"]()

    def kick(self, power=75):
        self._require("kick")
        return self._backend["kick"](max(0, percent(power)))

    def kickoff_wait(self):
        self._require("kickoff_wait")
        return self._backend["kickoff_wait"]()

    def kickoff_time(self):
        self._require("kickoff_time")
        return self._backend["kickoff_time"]()
