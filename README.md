# edu_robot_api

Eine Python-API zum Lernen und Programmieren mit Robotern. Roboter, Sensoren
und Aktoren werden als Objekte angesprochen; Messwerte und Steuerbefehle
verwenden eine gemeinsame Schnittstelle.

RoboWorkbench verwendet diese API für eigenständige virtuelle Lernroboter.
Ihre Eigenschaften werden durch das gewählte Modell und die Lernwelt bestimmt.

## Installation

Voraussetzung für die lokale Verwendung ist Python 3.11 oder neuer.
Nach dem Herunterladen dieses Repositorys im Hauptverzeichnis ausführen:

```powershell
python -m pip install ./wheels/edu_robot_api-0.6.0-py3-none-any.whl
```

Der Python-Import lautet:

```python
from edu_robot_api import Robot
```

Die Installation stellt die Klassen der Bibliothek bereit. Sie erzeugt allein
noch keinen Roboter und startet keine Simulation. Eine eigene Python-Anwendung
stellt das Roboterobjekt und dessen Ausführungsumgebung bereit.

Der Quelltext liegt in [core/](core/), das Installationspaket in [wheels/](wheels/).
[SHA256.json](SHA256.json) enthält die Prüfsummen der Dateien.

## Ein Programm in RoboWorkbench

In der Web-App ist keine lokale Installation nötig. Der Roboter des jeweiligen
Editors steht bei Programmstart bereits als `rob` bereit. Das Programm muss
keinen Roboternamen angeben und keine Verbindung aufbauen. Jeder Editor steuert
seinen eigenen Roboter.

Dieses Beispiel benötigt einen Front-Abstandssensor. Es fährt vorwärts, solange
der Abstand mindestens 25 cm beträgt, und hält andernfalls an:

```python
import time


def programm(rob):
    abstand = rob.sensors()["distance_front"]
    while True:
        wert = abstand.read()
        if wert is None or wert < 25:
            rob.stop()
        else:
            rob.forward(30)
        time.sleep(0.03)


programm(rob)
```

Die Web-App stoppt den Roboter und gibt seine Verbindung bei Programmende,
Fehler, Stop oder Reset frei. Im Anwendercode ist dafür kein `try/finally`
erforderlich. Fehler beim Sensorzugriff oder in der eigenen Logik sind
weiterhin möglich.

Bei zwei Robotern erhält jeder seinen eigenen Quelltext im jeweiligen Editor.
Beide Programme laufen nebenläufig; `time.sleep()` in einem Programm blockiert
das andere nicht. Die Variable `rob` bezeichnet in jedem Programm dessen eigenen
Roboter. Ein Zugriff auf den Roboter des anderen Editors ist nicht erlaubt.

## Sensoren und Aktoren

`rob.sensors()` und `rob.actuators()` liefern Dictionaries mit Bauteilobjekten.
Verfügbare Komponenten hängen vom ausgewählten Modell ab. Die Klasse beschreibt
die Fähigkeiten; der Name beschreibt die Verwendung einer konkreten Komponente.

```python
links = rob.sensors()["line_left"]
rechts = rob.sensors()["line_right"]
werte = rob.read_sensors([links, rechts])
print(werte[links], werte[rechts])
```

`sensor.read()` liest einen einzelnen Sensor. `rob.read_sensors()` liefert eine
gemeinsame Aufnahme. Deren Werte lassen sich über Sensorobjekt, aufgenommenen
Namen oder Position in der Auswahl abrufen. `None` bezeichnet einen fehlenden
Messwert. Ein nicht vorhandener Sensor oder eine fehlende Fähigkeit ist davon
zu unterscheiden und kann eine Exception auslösen.

## Bewegung und Einheiten

| Aufruf | Wirkung |
| --- | --- |
| `rob.forward(30)` | Vorwärts mit 30 Prozent Motorleistung |
| `rob.backward(30)` | Rückwärts mit 30 Prozent Motorleistung |
| `rob.drive(30, 10)` | Fahren mit positiver Lenkung nach rechts |
| `rob.stop()` | Motoren stoppen |
| `rob.set_speed(40)` | Standard-Motorleistung für nachfolgende Befehle setzen |

Abstände werden in Zentimetern, Winkel in Grad und Motorleistungen in Prozent
angegeben. Motorleistung ist keine garantierte Fahrgeschwindigkeit. Fahrverhalten
und Messwerte hängen vom Modell, der Welt und den Umgebungsbedingungen ab.

## Aufbau der API

`Robot` besitzt Sensor- und Aktorobjekte und delegiert Operationen an ein
`Backend`. Das ist ein Python-`Protocol`: Eine passende Implementierung stellt
die Methode `call(operation, *args)` bereit. `FunctionBackend` erfüllt diesen
Vertrag über eine Zuordnung von Operationsnamen zu Python-Funktionen.

![Klassendiagramm der API](docs/images/components.svg)

Die gefüllte Raute kennzeichnet Komposition, das hohle Dreieck Vererbung.
Die gestrichelte Verbindung von `FunctionBackend` zu `Backend` kennzeichnet die
strukturelle Erfüllung des Protokolls. Die Bibliothek enthält Typannotationen
und eine `py.typed`-Kennzeichnung für Typprüfwerkzeuge.

## Lizenz

Die Bibliothek steht unter [Apache-2.0](LICENSES/core-Apache-2.0.txt).
