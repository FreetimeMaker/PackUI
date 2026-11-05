#!/usr/bin/env python3
"""PackUI: a Qt frontend for locally installed Linux package managers."""

import configparser
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QRect, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
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


class DesktopCatalog:
    """Read presentation metadata only; package identities always come from the backend."""

    def __init__(self):
        self.entries = {}
        data_dirs = os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share"
        ).split(":")
        data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
        roots = [Path(p) / "applications" for p in data_dirs + [data_home]]
        roots += [
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications",
        ]
        for root in dict.fromkeys(roots):
            for path in sorted(root.glob("*.desktop")):
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    parser.read(path, encoding="utf-8")
                    entry = parser["Desktop Entry"]
                    if (
                        entry.get("Type") != "Application"
                        or entry.get("Hidden") == "true"
                    ):
                        continue
                    language = os.environ.get("LANG", "en").split(".")[0]
                    name = entry.get(
                        f"Name[{language}]",
                        entry.get(
                            f"Name[{language.split('_')[0]}]",
                            entry.get("Name", path.stem),
                        ),
                    )
                    summary = entry.get("Comment[de]", entry.get("Comment", ""))
                    self.entries[path.stem.casefold()] = (
                        name,
                        summary,
                        entry.get("Icon", ""),
                    )
                except (OSError, UnicodeError, configparser.Error, KeyError):
                    continue

    def presentation(self, package):
        key = re.sub(r"\.(?:x86_64|noarch|aarch64|i[3-6]86)$", "", package.name)
        key = key.split(":", 1)[0].casefold()
        name, summary, icon_name = self.entries.get(key, (package.name, "", key))
        icon = (
            QIcon(icon_name)
            if icon_name.startswith("/")
            else QIcon.fromTheme(icon_name)
        )
        if icon.isNull():
            icon = QIcon.fromTheme("application-x-executable")
        return (
            name,
            summary
            or package.description
            or "Weitere Informationen stellt die Paketquelle bereit.",
            icon,
        )


class AppCardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(5, 5, -7, -7)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(QColor("#9a85ee" if selected else "#dedeea"))
        painter.setBrush(
            QColor("#eee9ff" if selected else "#f8f7ff" if hover else "#ffffff")
        )
        painter.drawRoundedRect(rect, 16, 16)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_rect = QRect(rect.x() + 18, rect.y() + 20, 46, 46)
        if icon and not icon.isNull():
            icon.paint(painter, icon_rect)
        else:
            painter.setBrush(QColor("#e5ddff"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(icon_rect, 12, 12)
            painter.setPen(QColor("#6548bc"))
            painter.setFont(QFont("Sans Serif", 20, QFont.Weight.Bold))
            painter.drawText(
                icon_rect, Qt.AlignmentFlag.AlignCenter, index.data()[:1].upper()
            )
        x, width = rect.x() + 78, rect.width() - 96
        painter.setPen(QColor("#232137"))
        painter.setFont(QFont("Sans Serif", 11, QFont.Weight.Bold))
        painter.drawText(
            QRect(x, rect.y() + 21, width, 25),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(
                index.data(), Qt.TextElideMode.ElideRight, width
            ),
        )
        painter.setFont(QFont("Sans Serif", 9))
        painter.setPen(QColor("#777388"))
        painter.drawText(
            QRect(x, rect.y() + 48, width, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(
                index.data(Qt.ItemDataRole.UserRole + 2),
                Qt.TextElideMode.ElideRight,
                width,
            ),
        )
        painter.setPen(QColor("#625e73"))
        painter.drawText(
            rect.adjusted(18, 83, -18, -35),
            Qt.TextFlag.TextWordWrap,
            index.data(Qt.ItemDataRole.UserRole + 1),
        )
        painter.setPen(QColor("#7456bf"))
        painter.drawText(
            rect.adjusted(18, rect.height() - 30, -18, -8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            index.data(Qt.ItemDataRole.UserRole + 3),
        )
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(292, 184)


STORE_STYLE = """
QMainWindow, QDialog { background: #f6f6fb; color: #27243b; }
QWidget { font-family: 'Sans Serif'; font-size: 13px; color: #27243b; }
QFrame#sidebar { background: #eeedf6; border-right: 1px solid #e2e0ec; }
QLabel#brand { font-size: 26px; font-weight: 800; color: #6744c4; }
QLabel#muted { color: #79748b; }
QLabel#heading { font-size: 27px; font-weight: 750; }
QLabel#section { font-size: 18px; font-weight: 700; }
QFrame#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #39246d,stop:1 #7652cd); border-radius: 22px; }
QFrame#hero QLabel { color: white; background: transparent; }
QLabel#heroTitle { font-size: 33px; font-weight: 800; }
QPushButton { background: white; border: 1px solid #dfdce9; border-radius: 10px; padding: 10px 17px; font-weight: 600; }
QPushButton:hover { background: #eee8ff; border-color: #b5a1e7; }
QPushButton:disabled { color: #a6a0b5; background: #eeedf2; }
QPushButton#primary { background: #7350c8; color: white; border: none; }
QPushButton#primary:hover { background: #6040b4; }
QPushButton#nav { text-align: left; background: transparent; border: none; padding: 13px 15px; }
QPushButton#nav:checked { background: #dfd7f5; color: #603eaf; }
QLineEdit, QComboBox { background: white; border: 1px solid #dedbe8; border-radius: 10px; padding: 10px; selection-background-color: #7350c8; }
QListWidget { background: transparent; border: none; outline: none; }
QPlainTextEdit { background: #eeedf5; border: 1px solid #dedbe8; border-radius: 10px; padding: 8px; font-family: monospace; }
QProgressBar { border: none; background: #e8e2f5; border-radius: 2px; max-height: 4px; }
QProgressBar::chunk { background: #8059d7; }
QStatusBar { color: #79748b; background: #f6f6fb; }
QScrollBar:vertical { background: transparent; width: 9px; }
QScrollBar::handle:vertical { background: #c9c2d9; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class PackUIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PackUI – Entdecke deine nächste App")
        self.resize(1200, 820)
        self.setMinimumSize(820, 620)
        self.setStyleSheet(STORE_STYLE)
        self.catalog = DesktopCatalog()
        self.detail = None
        self.managers = PackageManager.detect()
        self.packages = []
        self.thread = None
        self.worker = None
        self.busy = False
        self.query_installed = True
        self.query_text = ""
        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 30, 20, 22)
        brand = QLabel("◈ PackUI")
        brand.setObjectName("brand")
        side.addWidget(brand)
        tagline = QLabel("Deine Apps. Deine Quellen.")
        tagline.setObjectName("muted")
        side.addWidget(tagline)
        side.addSpacing(35)
        self.discover_nav = QPushButton("◇   Entdecken")
        self.installed_nav = QPushButton("▦   Installiert")
        for button in (self.discover_nav, self.installed_nav):
            button.setObjectName("nav")
            button.setCheckable(True)
            side.addWidget(button)
        side.addStretch()
        source_label = QLabel("PAKETQUELLE")
        source_label.setObjectName("muted")
        side.addWidget(source_label)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 24, 25, 12)
        layout.setSpacing(18)
        controls = QHBoxLayout()
        self.manager = QComboBox()
        for manager in self.managers:
            self.manager.addItem(manager.name)
        self.mode = QComboBox()
        self.mode.addItems(["Installierte Pakete", "Pakete suchen"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Paketname oder Suchbegriff …")
        self.refresh = QPushButton("Laden / Suchen")
        side.addWidget(self.manager)
        source_note = QLabel("Direkt von deinen\nPaketquellen. Ohne Store-API.")
        source_note.setObjectName("muted")
        side.addWidget(source_note)
        self.mode.hide()
        self.search.setPlaceholderText("Apps und Pakete entdecken …")
        self.search.setClearButtonEnabled(True)
        self.refresh.setText("Suchen")
        self.refresh.setObjectName("primary")
        controls.addWidget(self.search, 1)
        controls.addWidget(self.refresh)
        self.log_toggle = QPushButton("Protokoll")
        self.log_toggle.setCheckable(True)
        controls.addWidget(self.log_toggle)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.pages = QStackedWidget()
        home = QWidget()
        home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(22)
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        hero_layout.addWidget(QLabel("DEIN LINUX. DEINE MÖGLICHKEITEN."))
        title = QLabel("Große Ideen.\nDie passenden Apps.")
        title.setObjectName("heroTitle")
        hero_layout.addWidget(title)
        subtitle = QLabel(
            "Finde neue Werkzeuge zum Gestalten, Arbeiten und Entdecken.\nInstalliert über die Paketquellen, denen du vertraust."
        )
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)
        hero_button = QPushButton("Kreativ werden  →")
        hero_button.clicked.connect(lambda: self.browse("Kreativ werden", "gimp"))
        hero_layout.addWidget(hero_button, 0, Qt.AlignmentFlag.AlignLeft)
        home_layout.addWidget(hero)
        label = QLabel("Was möchtest du machen?")
        label.setObjectName("section")
        home_layout.addWidget(label)
        categories = QGridLayout()
        categories.setSpacing(12)
        self.category_buttons = []
        for i, (title, subtitle, term) in enumerate(
            [
                ("◉  Internet", "Browser & Kommunikation", "browser"),
                ("✎  Kreativität", "Bildbearbeitung & Design", "gimp"),
                ("♫  Musik & Video", "Abspielen & Bearbeiten", "vlc"),
                ("▤  Produktivität", "Dokumente & Organisation", "office"),
                ("⌘  Entwicklung", "Editoren & Werkzeuge", "editor"),
                ("◇  Spiele", "Eine kleine Auszeit", "game"),
            ]
        ):
            button = QPushButton(title + "\n" + subtitle)
            button.setMinimumHeight(76)
            button.clicked.connect(
                lambda checked=False, t=title, q=term: self.browse(t, q)
            )
            categories.addWidget(button, i // 3, i % 3)
            self.category_buttons.append(button)
        self.category_buttons.append(hero_button)
        home_layout.addLayout(categories)
        note = QLabel(
            "Die Themen starten eine Suche in der gewählten Paketquelle.\nVerfügbarkeit und Beschreibungen hängen von deinen eingerichteten Repositories ab."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        home_layout.addWidget(note)
        home_layout.addStretch()
        self.pages.addWidget(home)
        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_title = QLabel("Deine Apps")
        self.results_title.setObjectName("heading")
        results_layout.addWidget(self.results_title)
        self.results_note = QLabel("")
        self.results_note.setObjectName("muted")
        results_layout.addWidget(self.results_note)
        self.cards = QListWidget()
        self.cards.setViewMode(QListView.ViewMode.IconMode)
        self.cards.setResizeMode(QListView.ResizeMode.Adjust)
        self.cards.setMovement(QListView.Movement.Static)
        self.cards.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cards.setWordWrap(True)
        self.cards.setMouseTracking(True)
        self.cards.setSpacing(0)
        self.cards.setItemDelegate(AppCardDelegate(self.cards))
        self.cards.setAccessibleName("Apps und Pakete")
        self.cards.itemClicked.connect(self.open_details)
        self.cards.itemActivated.connect(self.open_details)
        results_layout.addWidget(self.cards)
        self.empty = QLabel(
            "Keine Apps gefunden.\nVersuche einen anderen Suchbegriff oder eine andere Paketquelle."
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        results_layout.addWidget(self.empty)
        self.pages.addWidget(results)
        layout.addWidget(self.pages, 1)
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
        self.log.hide()
        self.log_toggle.toggled.connect(self.log.setVisible)
        layout.addWidget(self.log)
        shell.addWidget(sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(root)
        self.refresh.clicked.connect(self.load_packages)
        self.search.returnPressed.connect(self.load_packages)
        self.manager.currentIndexChanged.connect(self.source_changed)
        self.discover_nav.clicked.connect(self.show_discover)
        self.installed_nav.clicked.connect(self.show_installed)
        self.cards.itemSelectionChanged.connect(self.update_actions)
        self.install.clicked.connect(lambda: self.change_package(False))
        self.remove.clicked.connect(lambda: self.change_package(True))
        self.update_actions()
        self.show_discover()
        if not self.managers:
            self.refresh.setEnabled(False)
            self.installed_nav.setEnabled(False)
            for button in self.category_buttons:
                button.setEnabled(False)
            self.results_note.setText("Kein unterstützter Paketmanager installiert.")
            self.statusBar().showMessage(
                "Kein unterstützter Paketmanager gefunden (APT, DNF, Pacman, Zypper, Flatpak, Snap)."
            )

    def show_discover(self):
        if self.busy:
            return
        self.mode.setCurrentIndex(1)
        self.discover_nav.setChecked(True)
        self.installed_nav.setChecked(False)
        self.search.clear()
        self.reset_view()
        self.pages.setCurrentIndex(0)
        self.statusBar().showMessage(
            "Entdecke Apps aus deinen eingerichteten Paketquellen."
        )

    def show_installed(self):
        if self.busy:
            return
        self.mode.setCurrentIndex(0)
        self.discover_nav.setChecked(False)
        self.installed_nav.setChecked(True)
        self.search.clear()
        self.load_packages()

    def source_changed(self):
        if self.mode.currentIndex() == 0:
            self.show_installed()
        else:
            self.show_discover()

    def browse(self, title, query):
        if self.busy or not self.managers:
            return
        self.mode.setCurrentIndex(1)
        self.discover_nav.setChecked(True)
        self.installed_nav.setChecked(False)
        self.search.setText(query)
        self.load_packages()
        self.results_title.setText(title)

    def reset_view(self):
        self.packages = []
        self.cards.clear()
        if self.detail:
            self.detail.close()
            self.detail = None
        self.update_actions()

    def open_details(self, item):
        if self.busy:
            return
        package = self.packages[self.cards.row(item)]
        name, description, icon = self.catalog.presentation(package)
        dialog = QDialog(self)
        self.detail = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(name)
        dialog.setMinimumWidth(520)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(30, 30, 30, 30)
        box.setSpacing(18)
        header = QHBoxLayout()
        image = QLabel()
        image.setPixmap(icon.pixmap(72, 72))
        header.addWidget(image)
        title = QLabel(name)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setObjectName("heading")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        box.addLayout(header)
        summary = QLabel(description)
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        box.addWidget(summary)
        manager = self.managers[self.manager.currentIndex()]
        facts = QLabel(
            f"Paket: {package.name}\nVersion: {package.version or 'Von der Paketquelle bestimmt'}\nQuelle: {manager.name}\nInstallation: {package.scope or 'Standard des Paketmanagers'}"
        )
        facts.setTextFormat(Qt.TextFormat.PlainText)
        facts.setWordWrap(True)
        facts.setObjectName("muted")
        facts.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(facts)
        hint = QLabel(
            "Wird über deinen Paketmanager verwaltet. Abhängigkeiten können sich ändern."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        box.addWidget(hint)
        action = QPushButton("Entfernen" if self.query_installed else "Installieren")
        action.setObjectName("primary")
        action.clicked.connect(lambda: self.change_package(self.query_installed))
        box.addWidget(action)
        close = QPushButton("Zurück zum Store")
        close.clicked.connect(dialog.close)
        box.addWidget(close)
        dialog.finished.connect(lambda: setattr(self, "detail", None))
        dialog.open()

    def update_actions(self):
        selected = self.cards.currentRow() >= 0 and bool(self.cards.selectedItems())
        self.install.setEnabled(selected and not self.busy and not self.query_installed)
        self.remove.setEnabled(selected and not self.busy and self.query_installed)

    def start_command(self, command, callback, action=False):
        if self.busy:
            return
        self.busy = True
        for widget in (self.manager, self.mode, self.search, self.refresh):
            widget.setEnabled(False)
        for widget in (self.discover_nav, self.installed_nav, *self.category_buttons):
            widget.setEnabled(False)
        if self.detail:
            for button in self.detail.findChildren(QPushButton):
                button.setEnabled(False)
        self.progress.show()
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
        self.progress.hide()
        for widget in (self.discover_nav, self.installed_nav, *self.category_buttons):
            widget.setEnabled(bool(self.managers))
        if self.detail:
            for button in self.detail.findChildren(QPushButton):
                button.setEnabled(True)
        for widget in (self.manager, self.mode, self.search, self.refresh):
            widget.setEnabled(True)
        self.update_actions()

    def show_error(self, message):
        self.log.appendPlainText(message)
        self.statusBar().showMessage("Vorgang fehlgeschlagen – siehe Protokoll.")
        self.results_note.setText(
            "Die Paketquelle konnte nicht geladen werden. Details stehen im Protokoll."
        )
        self.log_toggle.setChecked(True)
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
        self.pages.setCurrentIndex(1)
        self.empty.hide()
        self.empty.setText(
            "Keine Apps gefunden.\nVersuche einen anderen Suchbegriff oder eine andere Paketquelle."
        )
        self.results_title.setText(
            "Installiert"
            if self.query_installed
            else f"Ergebnisse für „{self.query_text}“"
        )
        self.results_note.setText("Deine Paketquelle wird durchsucht …")
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
        self.cards.clear()
        for package in self.packages:
            name, description, icon = self.catalog.presentation(package)
            item = QListWidgetItem(icon, name)
            item.setData(Qt.ItemDataRole.UserRole + 1, description)
            item.setData(Qt.ItemDataRole.UserRole + 2, package.version or manager.name)
            item.setData(
                Qt.ItemDataRole.UserRole + 3,
                "Installiert · " + manager.name
                if self.query_installed
                else "Verfügbar · " + manager.name,
            )
            item.setToolTip(name + "\n" + description + "\n" + package.name)
            item.setSizeHint(QSize(292, 184))
            self.cards.addItem(item)
        self.empty.setVisible(not self.packages)
        self.results_note.setText(
            f"{len(self.packages)} Apps und Pakete · {manager.name} · Wähle eine Karte für Details"
        )
        self.statusBar().showMessage(f"{len(self.packages)} Pakete · {manager.name}")

    def change_package(self, remove):
        row = self.cards.currentRow()
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
            "Paketänderung erfolgreich. Mit der Suche oder „Installiert“ die Ansicht aktualisieren."
        )
        self.statusBar().showMessage(
            "Paketänderung abgeschlossen – Liste bitte neu laden."
        )
        self.reset_view()
        self.empty.setText(
            "Paketänderung abgeschlossen.\nÖffne „Installiert“ oder starte eine neue Suche."
        )
        self.empty.show()
        self.results_note.setText("Erfolgreich abgeschlossen")

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
