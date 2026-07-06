import subprocess
import unittest
from datetime import datetime, timezone
from unittest.mock import mock_open, patch

from services.health_manager import UNKNOWN, HealthManager
from services.worker_manager import WorkerManager


class HealthManagerTests(unittest.TestCase):
    def test_get_health_contains_expected_sections(self) -> None:
        worker_manager = WorkerManager(host="worker.local", idle_timeout_seconds=900)
        health_manager = HealthManager(worker_manager)

        with patch.object(worker_manager, "is_online", return_value=True), patch.object(
            health_manager,
            "_disk_usage_percent",
            return_value=50.0,
        ), patch.object(
            health_manager,
            "_memory_usage_percent",
            return_value=25.0,
        ), patch.object(
            health_manager,
            "_load_average",
            return_value={"1m": 0.1, "5m": 0.2, "15m": 0.3},
        ), patch.object(
            health_manager,
            "_services_health",
            return_value={"seesam_hub": "active", "tailscale": "unknown"},
        ), patch.object(
            health_manager,
            "_updates_health",
            return_value={"apt_updates_available_count": 2},
        ), patch.object(
            health_manager,
            "_uptime_seconds",
            return_value=123,
        ):
            health = health_manager.get_health()

        self.assertEqual(health["hub"]["status"], "ok")
        self.assertEqual(health["hub"]["uptime_seconds"], 123)
        self.assertEqual(health["worker"]["host"], "worker.local")
        self.assertTrue(health["worker"]["online"])
        self.assertEqual(health["system"]["disk_usage_percent"], 50.0)
        self.assertEqual(health["services"]["seesam_hub"], "active")
        self.assertEqual(health["updates"]["apt_updates_available_count"], 2)

    def test_worker_last_used_at_is_serialized(self) -> None:
        worker_manager = WorkerManager()
        worker_manager.last_used_at = datetime(2026, 7, 6, tzinfo=timezone.utc)
        health_manager = HealthManager(worker_manager)

        with patch.object(worker_manager, "is_online", return_value=False):
            worker_health = health_manager._worker_health()

        self.assertEqual(worker_health["last_used_at"], "2026-07-06T00:00:00+00:00")

    def test_failed_worker_online_check_returns_unknown(self) -> None:
        worker_manager = WorkerManager()
        health_manager = HealthManager(worker_manager)

        with patch.object(worker_manager, "is_online", side_effect=OSError):
            self.assertEqual(health_manager._safe_worker_online(), UNKNOWN)

    def test_uptime_returns_unknown_when_proc_read_fails(self) -> None:
        health_manager = HealthManager(WorkerManager())

        with patch("builtins.open", side_effect=OSError):
            self.assertEqual(health_manager._uptime_seconds(), UNKNOWN)

    def test_memory_usage_uses_memavailable(self) -> None:
        health_manager = HealthManager(WorkerManager())
        meminfo = "MemTotal:       1000 kB\nMemAvailable:    250 kB\n"

        with patch("builtins.open", mock_open(read_data=meminfo)):
            self.assertEqual(health_manager._memory_usage_percent(), 75.0)

    def test_service_status_returns_unknown_when_command_fails(self) -> None:
        health_manager = HealthManager(WorkerManager())

        with patch.object(health_manager, "_run_read_only_command", return_value=None):
            self.assertEqual(health_manager._systemd_service_status("seesam-hub"), UNKNOWN)

    def test_apt_update_count_ignores_listing_header(self) -> None:
        health_manager = HealthManager(WorkerManager())
        result = subprocess.CompletedProcess(
            args=["apt"],
            returncode=0,
            stdout="Listing...\npackage-a/stable 1 amd64 [upgradable]\n\npackage-b/stable 2 amd64 [upgradable]\n",
            stderr="",
        )

        with patch.object(health_manager, "_run_read_only_command", return_value=result):
            self.assertEqual(health_manager._apt_updates_available_count(), 2)


if __name__ == "__main__":
    unittest.main()
