#!/usr/bin/env python3
"""PackUI: a Qt frontend for locally installed Linux package managers."""

import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class Package:
    name: str
    version: str = ""
    description: str = ""
    scope: str = ""


class PackageManager:
    """Build argument lists, never shell commands, from package identifiers."""

    def __init__(self, name, executable):
        self.name = name
        self.executable = executable

    @classmethod
    def detect(cls):
        candidates = [
            ("APT", "apt-get"),
            ("DNF", "dnf"),
            ("Pacman", "pacman"),
            ("Zypper", "zypper"),
            ("Flatpak", "flatpak"),
            ("Snap", "snap"),
        ]
        result = []
        for name, executable in candidates:
            path = shutil.which(executable)
            if not path:
                continue
            if name == "APT" and not all(
                shutil.which(p) for p in ("apt-cache", "dpkg-query")
            ):
                continue
            result.append(cls(name, path))
        return result

    def query_command(self, installed, query):
        if not installed and not query.strip():
            raise ValueError("Bitte einen Suchbegriff eingeben.")
        if self.name == "APT":
            if installed:
                return [
                    shutil.which("dpkg-query"),
                    "-W",
                    "-f=${binary:Package}\\t${Version}\\t${db:Status-Status}\\n",
                ]
            return [shutil.which("apt-cache"), "search", "--", re.escape(query)]
        if self.name == "DNF":
            if installed:
                return [self.executable, "-q", "list", "--installed"]
            return [
                self.executable,
                "-q",
                "list",
                "--available",
                "--",
                "*" + query + "*",
            ]
        if self.name == "Pacman":
            return (
                [self.executable, "-Q"]
                if installed
                else [self.executable, "-Ss", "--", re.escape(query)]
            )
        if self.name == "Zypper":
            return [self.executable, "--non-interactive", "search", "--details"] + (
                ["--installed-only"] if installed else ["--", query]
            )
        if self.name == "Flatpak":
            return (
                [
                    self.executable,
                    "list",
                    "--app",
                    "--columns=application,version,name,installation",
                ]
                if installed
                else [
                    self.executable,
                    "search",
                    "--columns=application,version,name,description",
                    "--",
                    query,
                ]
            )
        return (
            [self.executable, "list"]
            if installed
            else [self.executable, "find", "--", query]
        )

    def parse(self, output, installed):
        packages = []
        lines = output.splitlines()
        for line in lines:
            if not line.strip():
                continue
            if self.name == "APT":
                if installed:
                    fields = line.split("\t")
                    if len(fields) >= 3 and fields[2] == "installed":
                        packages.append(Package(fields[0], fields[1]))
                elif " - " in line:
                    name, description = line.split(" - ", 1)
                    packages.append(Package(name, description=description))
            elif self.name == "DNF":
                fields = line.split()
                if len(fields) == 3 and re.fullmatch(
                    r"[A-Za-z0-9_+.-]+\.(?:noarch|x86_64|i[3-6]86|aarch64|armv\w+|ppc64le|s390x|riscv64|src)",
                    fields[0],
                ):
                    packages.append(Package(fields[0], fields[1], fields[2]))
            elif self.name == "Pacman":
                if installed:
                    fields = line.split(maxsplit=1)
                    if len(fields) == 2:
                        packages.append(Package(*fields))
                elif not line.startswith(" ") and "/" in line:
                    fields = line.split()
                    packages.append(Package(fields[0].split("/", 1)[1], fields[1]))
                elif packages and line.startswith(" "):
                    previous = packages[-1]
                    packages[-1] = Package(
                        previous.name, previous.version, line.strip()
                    )
            elif self.name == "Zypper":
                fields = [field.strip() for field in line.split("|")]
                if len(fields) == 6 and fields[2] == "package":
                    packages.append(Package(fields[1], fields[3], fields[5]))
            elif self.name == "Flatpak":
                fields = line.split("\t")
                if len(fields) >= 3:
                    packages.append(
                        Package(
                            fields[0],
                            fields[1],
                            fields[2] if installed else " — ".join(fields[2:]),
                            fields[3] if installed and len(fields) > 3 else "",
                        )
                    )
            elif self.name == "Snap":
                fields = line.split(None, 5)
                if fields[0] == "Name" or len(fields) < 5:
                    continue
                packages.append(Package(fields[0], fields[1], fields[-1]))
        return list(dict.fromkeys(packages))

    def action_command(self, package, remove=False):
        # Reject options and control characters even when a backend emits unexpected output.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+:@/~-]*", package.name):
            raise ValueError("Ungültige Paketkennung.")
        name = package.name
        if self.name == "APT":
            command = [
                self.executable,
                "-y",
                "remove" if remove else "install",
                "--",
                name,
            ]
        elif self.name == "DNF":
            command = [
                self.executable,
                "-y",
                "remove" if remove else "install",
                "--",
                name,
            ]
        elif self.name == "Pacman":
            command = [
                self.executable,
                "--noconfirm",
                "-R" if remove else "-S",
                "--",
                name,
            ]
        elif self.name == "Zypper":
            command = [
                self.executable,
                "--non-interactive",
                "remove" if remove else "install",
                "--",
                name,
            ]
        elif self.name == "Flatpak":
            scope = package.scope or "user"
            if scope not in ("user", "system"):
                raise ValueError(
                    "Diese benannte Flatpak-Installation wird nicht unterstützt."
                )
            return [
                self.executable,
                "uninstall" if remove else "install",
                "--" + scope,
                "-y",
                "--",
                name,
            ]
        else:
            command = [self.executable, "remove" if remove else "install", "--", name]
        if os.geteuid() != 0:
            pkexec = shutil.which("pkexec")
            if not pkexec:
                raise RuntimeError(
                    "Für Systemänderungen wird pkexec (Polkit) benötigt."
                )
            command.insert(0, pkexec)
        return command


class CommandWorker(QObject):
    output = pyqtSignal(str)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command, action=False):
        super().__init__()
        self.command = command
        self.action = action

    def run(self):
        try:
            environment = dict(
                os.environ, LC_ALL="C", LANG="C", TERM="dumb", NO_COLOR="1"
            )
            if self.action:
                # Stream changes to the log; never kill a package transaction on a timeout.
                with subprocess.Popen(
                    self.command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    env=environment,
                ) as process:
                    for line in process.stdout:
                        self.output.emit(line.rstrip())
                    code = process.wait()
                if code:
                    raise RuntimeError(
                        f"Paketmanager wurde mit Status {code} beendet. Details stehen im Protokoll."
                    )
                self.succeeded.emit("")
            else:
                result = subprocess.run(
                    self.command,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    env=environment,
                    timeout=120,
                )
                if result.returncode:
                    raise RuntimeError(
                        result.stderr.strip()
                        or result.stdout.strip()
                        or f"Status {result.returncode}"
                    )
                self.succeeded.emit(result.stdout)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class PackUIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PackUI – Paketverwaltung")
        self.resize(1050, 720)
        self.managers = PackageManager.detect()
        self.packages = []
        self.thread = None
        self.worker = None
        self.busy = False
        self.query_installed = True
        self.query_text = ""
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = QHBoxLayout()
        self.manager = QComboBox()
        for manager in self.managers:
            self.manager.addItem(manager.name)
        self.mode = QComboBox()
        self.mode.addItems(["Installierte Pakete", "Pakete suchen"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Paketname oder Suchbegriff …")
        self.refresh = QPushButton("Laden / Suchen")
        for widget in (self.manager, self.mode, self.search, self.refresh):
            controls.addWidget(widget)
        layout.addLayout(controls)
        layout.addWidget(
            QLabel(
                "Lokale Paketmanager · keine Store-API · Repository-Zugriffe durch den Paketmanager möglich"
            )
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Paket", "Version", "Beschreibung / Quelle", "Installation"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.install = QPushButton("Installieren")
        self.remove = QPushButton("Entfernen")
        actions.addStretch()
        actions.addWidget(self.install)
        actions.addWidget(self.remove)
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setMaximumHeight(180)
        layout.addWidget(self.log)
        self.setCentralWidget(root)
        self.refresh.clicked.connect(self.load_packages)
        self.search.returnPressed.connect(self.load_packages)
        self.manager.currentIndexChanged.connect(self.reset_view)
        self.mode.currentIndexChanged.connect(self.reset_view)
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.install.clicked.connect(lambda: self.change_package(False))
        self.remove.clicked.connect(lambda: self.change_package(True))
        self.update_actions()
        if self.managers:
            self.load_packages()
        else:
            self.refresh.setEnabled(False)
            self.statusBar().showMessage(
                "Kein unterstützter Paketmanager gefunden (APT, DNF, Pacman, Zypper, Flatpak, Snap)."
            )

    def reset_view(self):
        self.packages = []
        self.table.setRowCount(0)
        self.update_actions()

    def update_actions(self):
        selected = self.table.currentRow() >= 0 and bool(self.table.selectedItems())
        self.install.setEnabled(selected and not self.busy and not self.query_installed)
        self.remove.setEnabled(selected and not self.busy and self.query_installed)

    def start_command(self, command, callback, action=False):
        if self.busy:
            return
        self.busy = True
        for widget in (self.manager, self.mode, self.search, self.refresh):
            widget.setEnabled(False)
        self.update_actions()
        self.log.appendPlainText("$ " + shlex.join(command))
        self.statusBar().showMessage("Paketmanager arbeitet …")
        self.thread = QThread(self)
        self.worker = CommandWorker(command, action)
        self.worker.moveToThread(self.thread)
        self.worker.output.connect(self.log.appendPlainText)
        self.worker.succeeded.connect(callback)
        self.worker.failed.connect(self.show_error)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.command_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def command_finished(self):
        self.busy = False
        self.worker = None
        self.thread = None
        for widget in (self.manager, self.mode, self.search, self.refresh):
            widget.setEnabled(True)
        self.update_actions()

    def show_error(self, message):
        self.log.appendPlainText(message)
        self.statusBar().showMessage("Vorgang fehlgeschlagen – siehe Protokoll.")
        QMessageBox.warning(self, "Paketmanager", message)

    def load_packages(self):
        if self.busy or not self.managers:
            return
        self.query_installed = self.mode.currentIndex() == 0
        self.query_text = self.search.text().strip()
        manager = self.managers[self.manager.currentIndex()]
        try:
            command = manager.query_command(self.query_installed, self.query_text)
        except ValueError as error:
            self.show_error(str(error))
            return
        self.reset_view()
        self.start_command(command, self.packages_loaded)

    def packages_loaded(self, output):
        manager = self.managers[self.manager.currentIndex()]
        packages = manager.parse(output, self.query_installed)
        if self.query_installed and self.query_text:
            query = self.query_text.casefold()
            packages = [
                p
                for p in packages
                if query in (p.name + " " + p.description).casefold()
            ]
        self.packages = sorted(
            packages, key=lambda package: (package.name.casefold(), package.scope)
        )
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.packages))
        for row, package in enumerate(self.packages):
            for column, value in enumerate(
                (package.name, package.version, package.description, package.scope)
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.statusBar().showMessage(f"{len(self.packages)} Pakete · {manager.name}")

    def change_package(self, remove):
        row = self.table.currentRow()
        if self.busy or row < 0 or row >= len(self.packages):
            return
        package = self.packages[row]
        manager = self.managers[self.manager.currentIndex()]
        try:
            command = manager.action_command(package, remove)
        except (ValueError, RuntimeError) as error:
            self.show_error(str(error))
            return
        verb = "entfernen" if remove else "installieren"
        message = (
            f"{package.name} mit {manager.name} {verb}?\n\n"
            "Der Paketmanager kann dabei auch Abhängigkeiten ändern.\n"
            "Prüfe das Protokoll. Für Systempakete erscheint gegebenenfalls eine Passwortabfrage.\n\n"
            + shlex.join(command)
        )
        if (
            QMessageBox.question(
                self,
                "Paketänderung bestätigen",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.start_command(command, self.action_finished, action=True)

    def action_finished(self, output):
        self.log.appendPlainText(
            "Paketänderung erfolgreich. Liste mit „Laden / Suchen“ aktualisieren."
        )
        self.statusBar().showMessage(
            "Paketänderung abgeschlossen – Liste bitte neu laden."
        )
        self.reset_view()

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(
                self, "Vorgang läuft", "Bitte warten, bis der Paketmanager fertig ist."
            )
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PackUI")
    window = PackUIWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
