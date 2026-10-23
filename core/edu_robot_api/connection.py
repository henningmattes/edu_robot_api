"""Optional legacy connection hook. Explicit Bridge objects need no discovery."""
from importlib.metadata import entry_points


def connect_robot(name=None, **options):
    connectors = list(entry_points(group="edu_robot_api.connectors", name="default"))
    if len(connectors) != 1:
        raise RuntimeError("Für diesen Verbindungsaufruf genau ein passendes Verbindungspaket installieren oder Robot.connect(bridge=...) verwenden.")
    return connectors[0].load()(name, **options)
