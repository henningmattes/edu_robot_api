"""Optional native image helpers; the public camera data remains portable RGB."""

def camera_rgb(robot):
    """Full camera image as a portable RGB dictionary (width, height, pixels).

    The same learner call works in CPython and the browser. NumPy is not needed.
    """
    return robot.sensors()["camera"].read() if hasattr(robot, "read_sensors") else robot.camera_image()


def rgb_array(image):
    import numpy as np
    if image is None:
        return None
    pixels = np.asarray(image["pixels"], dtype=np.uint32).reshape(image["height"], image["width"])
    return np.stack(((pixels >> 16) & 255, (pixels >> 8) & 255, pixels & 255), axis=-1).astype(np.uint8)


def camera_bgr(robot):
    image = rgb_array(camera_rgb(robot))
    return None if image is None else image[:, :, ::-1].copy()
