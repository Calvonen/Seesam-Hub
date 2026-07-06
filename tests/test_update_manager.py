import subprocess
import unittest
from unittest.mock import patch

from services.update_manager import UNKNOWN, UpdateManager


class UpdateManagerTests(unittest.TestCase):
    def test_get_update_status_contains_apt_and_firmware(self) -> None:
        update_manager = UpdateManager()

        with patch.object(
            update_manager,
            "_apt_status",
            return_value={"updates_available_count": 1, "packages": ["bash"]},
        ), patch.object(
            update_manager,
            "_firmware_status",
            return_value={
                "updates_available": False,
                "updates_available_count": 0,
                "summaries": [],
            },
        ):
            status = update_manager.get_update_status()

        self.assertEqual(status["apt"]["updates_available_count"], 1)
        self.assertEqual(status["firmware"]["updates_available"], False)

    def test_apt_status_reports_count_and_package_names(self) -> None:
        update_manager = UpdateManager()
        result = subprocess.CompletedProcess(
            args=["apt"],
            returncode=0,
            stdout=(
                "Listing...\n"
                "Listataan...\n"
                "bash/stable 5.2 amd64 [upgradable]\n"
                "curl/stable 8.0 amd64 [upgradable]\n"
            ),
            stderr="",
        )

        with patch.object(update_manager, "_run_read_only_command", return_value=result):
            status = update_manager._apt_status()

        self.assertEqual(status["updates_available_count"], 2)
        self.assertEqual(status["packages"], ["bash", "curl"])

    def test_apt_status_returns_unknown_when_command_fails(self) -> None:
        update_manager = UpdateManager()

        with patch.object(update_manager, "_run_read_only_command", return_value=None):
            status = update_manager._apt_status()

        self.assertEqual(status["updates_available_count"], UNKNOWN)
        self.assertEqual(status["packages"], UNKNOWN)

    def test_firmware_status_reports_updates_from_json(self) -> None:
        update_manager = UpdateManager()
        result = subprocess.CompletedProcess(
            args=["fwupdmgr"],
            returncode=0,
            stdout=(
                '{"Devices":[{"Name":"UEFI dbx","Releases":[{"Version":"2026.1",'
                '"Checksums":[{"Name":"internal checksum"}]}]}]}'
            ),
            stderr="",
        )

        with patch.object(update_manager, "_run_read_only_command", return_value=result):
            status = update_manager._firmware_status()

        self.assertTrue(status["updates_available"])
        self.assertEqual(status["updates_available_count"], 1)
        self.assertEqual(status["summaries"], ["UEFI dbx 2026.1"])

    def test_firmware_status_reports_no_updates_from_text(self) -> None:
        update_manager = UpdateManager()
        result = subprocess.CompletedProcess(
            args=["fwupdmgr"],
            returncode=0,
            stdout="No upgrades for device",
            stderr="",
        )

        with patch.object(update_manager, "_run_read_only_command", return_value=result):
            status = update_manager._firmware_status()

        self.assertEqual(status["updates_available"], False)
        self.assertEqual(status["updates_available_count"], 0)
        self.assertEqual(status["summaries"], [])

    def test_firmware_status_returns_unknown_when_command_fails(self) -> None:
        update_manager = UpdateManager()

        with patch.object(update_manager, "_run_read_only_command", return_value=None):
            status = update_manager._firmware_status()

        self.assertEqual(status["updates_available"], UNKNOWN)
        self.assertEqual(status["updates_available_count"], UNKNOWN)
        self.assertEqual(status["summaries"], UNKNOWN)


if __name__ == "__main__":
    unittest.main()
