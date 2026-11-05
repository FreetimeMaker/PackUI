"""Offline tests: no package transactions or network access."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from packui import CommandWorker, Package, PackageManager, PackUIWindow


class BackendTests(unittest.TestCase):
    def manager(self, name):
        return PackageManager(name, "/usr/bin/manager")

    def test_apt(self):
        manager = self.manager("APT")
        self.assertEqual(
            manager.parse("vim\t9.0\tinstalled\nold\t1\tconfig-files\n", True),
            [Package("vim", "9.0")],
        )
        self.assertEqual(
            manager.parse("vim - editor\n", False),
            [Package("vim", description="editor")],
        )

    def test_dnf4_and_dnf5_lists(self):
        output = "Installed Packages\nvim.x86_64 9.0 @updates\nAvailable Packages\nvim.noarch 9.1 fedora\n"
        for installed in (True, False):
            self.assertEqual(len(self.manager("DNF").parse(output, installed)), 2)
        self.assertIn("--available", self.manager("DNF").query_command(False, "vim"))

    def test_pacman(self):
        self.assertEqual(
            self.manager("Pacman").parse(
                "extra/vim 9.0 [installed]\n    Editor\n", False
            ),
            [Package("vim", "9.0", "Editor")],
        )
        self.assertEqual(
            self.manager("Pacman").parse("vim 9.0\n", True), [Package("vim", "9.0")]
        )

    def test_zypper(self):
        output = "S | Name | Type | Version | Arch | Repository\ni+ | vim | package | 9.0 | x86_64 | Main\n"
        self.assertEqual(
            self.manager("Zypper").parse(output, True), [Package("vim", "9.0", "Main")]
        )

    def test_flatpak_scope(self):
        manager = self.manager("Flatpak")
        packages = manager.parse("org.example.App\t1.0\tExample\tsystem\n", True)
        self.assertEqual(
            packages, [Package("org.example.App", "1.0", "Example", "system")]
        )
        self.assertIn("--system", manager.action_command(packages[0], True))
        self.assertIn("--user", manager.action_command(Package("org.example.App")))
        with self.assertRaises(ValueError):
            manager.action_command(Package("org.example.App", scope="custom"), True)

    def test_snap(self):
        output = "Name Version Rev Tracking Publisher Notes\nhello 1.0 5 latest/stable example -\n"
        self.assertEqual(
            self.manager("Snap").parse(output, True), [Package("hello", "1.0", "-")]
        )

    def test_no_options_or_shell_injection(self):
        for name in ("APT", "DNF", "Pacman", "Zypper", "Flatpak", "Snap"):
            for identifier in ("--help", "x;touch /tmp/bad", "x\ny", "$(id)"):
                with (
                    self.subTest(name=name, identifier=identifier),
                    self.assertRaises(ValueError),
                ):
                    self.manager(name).action_command(Package(identifier))

    @patch("packui.os.geteuid", return_value=1000)
    @patch("packui.shutil.which", return_value="/usr/bin/pkexec")
    def test_system_changes_use_pkexec(self, which, uid):
        command = self.manager("APT").action_command(Package("vim:amd64"))
        self.assertEqual(command[0], "/usr/bin/pkexec")
        self.assertEqual(command[-2:], ["--", "vim:amd64"])

    @patch("packui.os.geteuid", return_value=1000)
    @patch("packui.shutil.which", return_value=None)
    def test_missing_pkexec(self, which, uid):
        with self.assertRaises(RuntimeError):
            self.manager("DNF").action_command(Package("vim"))

    def test_empty_search(self):
        for name in ("APT", "DNF", "Pacman", "Zypper", "Flatpak", "Snap"):
            with self.assertRaises(ValueError):
                self.manager(name).query_command(False, " ")


class QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("packui.PackageManager.detect", return_value=[])
    def test_window_without_backend(self, detect):
        window = PackUIWindow()
        self.assertFalse(window.refresh.isEnabled())
        self.assertFalse(window.install.isEnabled())
        window.close()

    @patch("packui.PackUIWindow.load_packages")
    @patch(
        "packui.PackageManager.detect",
        return_value=[PackageManager("APT", "/usr/bin/apt-get")],
    )
    def test_package_display_and_actions(self, detect, load):
        window = PackUIWindow()
        window.packages_loaded("vim\t9.0\tinstalled\n")
        self.assertEqual(window.table.item(0, 0).text(), "vim")
        window.table.selectRow(0)
        self.assertTrue(window.remove.isEnabled())
        self.assertFalse(window.install.isEnabled())
        window.reset_view()
        self.assertFalse(window.remove.isEnabled())
        window.close()

    def test_worker_query_success(self):
        import sys

        worker = CommandWorker([sys.executable, "-c", "print('ok')"])
        success = QSignalSpy(worker.succeeded)
        finished = QSignalSpy(worker.finished)
        worker.run()
        self.assertEqual(success[0][0], "ok\n")
        self.assertEqual(len(finished), 1)

    def test_worker_reports_failure(self):
        import sys

        worker = CommandWorker([sys.executable, "-c", "import sys; sys.exit(3)"])
        failed = QSignalSpy(worker.failed)
        worker.run()
        self.assertEqual(len(failed), 1)


if __name__ == "__main__":
    unittest.main()
