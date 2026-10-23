"""Optional legacy connection hook. Explicit Bridge objects need no discovery."""
from importlib.metadata import entry_points


def connect_robot(name=None, **options):
    connectors = list(entry_points(group="edu_robot_api.connectors", name="default"))
    if len(connectors) != 1:
        raise RuntimeError(
            "No unambiguous default connection is configured. "
            "Use Robot.connect(bridge=...) with a bridge supplied by your application."
        )
    return connectors[0].load()(name, **options)
