# PackUI

PackUI ist eine Linux-Paketverwaltung mit **Python 3 und PyQt6**. Sie nutzt die auf dem Rechner installierten Paketmanager direkt – keine Store-API, kein Supabase und keine Anmeldung.

## Funktionen

- Automatische Erkennung von **APT, DNF, Pacman, Zypper, Flatpak und Snap**.
- Paketmanager auswählen, installierte Pakete anzeigen und nach Namen filtern.
- Verfügbare Pakete suchen (bei DNF nach Paketnamen).
- Pakete nach expliziter Bestätigung installieren oder entfernen.
- Befehle und Transaktionsausgaben im Protokoll anzeigen.
- Paketmanager laufen in einem Hintergrundthread; die Oberfläche bleibt reaktionsfähig.

## Starten

Voraussetzungen: Python >= 3.9, PyQt6 und mindestens einer der unterstützten Paketmanager. Für Änderungen an Systempaketen wird zusätzlich `pkexec` mit einem laufenden Polkit-Authentifizierungsagenten benötigt. **PackUI nicht mit sudo starten.**

Debian / Ubuntu:

```bash
sudo apt install python3-pyqt6 policykit-1
python3 packui.py
```

Fedora:

```bash
sudo dnf install python3-pyqt6 polkit
python3 packui.py
```

Alternativ in einer virtuellen Umgebung:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python packui.py
```

## Bedienung und Grenzen

1. Paketmanager und Ansicht wählen.
2. Optional einen Filter eingeben; bei „Pakete suchen“ ist ein Suchbegriff erforderlich.
3. „Laden / Suchen“ drücken, eine Zeile auswählen und installieren oder entfernen.
4. Nach einer Änderung die Paketliste erneut laden.

PackUI verwaltet keine eigenen Paketquellen und aktualisiert nicht automatisch alle Pakete. Die Paketmanager verwenden ihre vorhandene Konfiguration, Paketlisten und Repositories. Suche und Installation können deshalb Netzwerkzugriffe auslösen. Flatpak-Neuinstallationen erfolgen für den aktuellen Benutzer und benötigen einen bereits konfigurierten Benutzer-Remote. Beim Entfernen wird die ermittelte Benutzer-/Systeminstallation verwendet; benannte Flatpak-Installationen werden nicht unterstützt. Snap benötigt einen laufenden snapd-Dienst.

Systemänderungen können auch Abhängigkeiten betreffen. PackUI bestätigt den gewählten Befehl vorab, führt den Paketmanager danach jedoch nichtinteraktiv aus. Es zeigt keine separate Vorschau aller Abhängigkeitsänderungen. Während ein Vorgang läuft, sind weitere Befehle und das Schließen des Fensters gesperrt, damit keine Pakettransaktion abgebrochen wird. Leseabfragen haben ein Zeitlimit von 120 Sekunden, Änderungen bewusst nicht.

## Installation und Pakete bauen

```bash
sudo make install
make deb
make rpm
sudo make uninstall
```

Die Installation verwendet das systemweite PyQt6; es werden keine Python-Abhängigkeiten mit Root-Pip nachinstalliert. Zum Paketbau werden `dpkg-deb` beziehungsweise `rpmbuild` benötigt.

## Tests

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest -v test_packui
python3 -m py_compile packui.py
```

Die Tests verwenden Beispielausgaben und führen keine Paketänderungen aus.
