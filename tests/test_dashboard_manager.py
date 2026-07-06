import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from services.dashboard_manager import UNKNOWN, DashboardManager
from services.health_manager import HealthManager
from services.update_manager import UpdateManager
from services.worker_manager import WorkerManager


class DashboardManagerTests(unittest.TestCase):
    def test_get_dashboard_combines_expected_sections(self) -> None:
        worker_manager = WorkerManager(host="worker.local", idle_timeout_seconds=900)
        worker_manager.last_used_at = datetime(2026, 7, 6, tzinfo=timezone.utc)
        health_manager = HealthManager(worker_manager)
        update_manager = UpdateManager()
        dashboard_manager = DashboardManager(
            health_manager=health_manager,
            update_manager=update_manager,
            worker_manager=worker_manager,
        )

        with patch.object(
            health_manager,
            "_hub_health",
            return_value={"status": "ok", "hostname": "hub"},
        ), patch.object(
            health_manager,
            "_system_health",
            return_value={"disk_usage_percent": 22.0},
        ), patch.object(
            health_manager,
            "_services_health",
            return_value={"seesam_hub": "active", "tailscale": "inactive"},
        ), patch.object(
            update_manager,
            "get_update_status",
            return_value={
                "apt": {"updates_available_count": 2, "packages": ["bash", "curl"]},
                "firmware": {
                    "updates_available": True,
                    "updates_available_count": 1,
                    "summaries": ["UEFI dbx 2026.1"],
                },
            },
        ), patch.object(
            worker_manager,
            "is_online",
            return_value=True,
        ):
            dashboard = dashboard_manager.get_dashboard()

        self.assertEqual(dashboard["hub"]["status"], "ok")
        self.assertEqual(dashboard["worker"]["host"], "worker.local")
        self.assertTrue(dashboard["worker"]["online"])
        self.assertEqual(
            dashboard["worker"]["last_used_at"],
            "2026-07-06T00:00:00+00:00",
        )
        self.assertEqual(dashboard["system"]["disk_usage_percent"], 22.0)
        self.assertEqual(dashboard["services"]["seesam_hub"], "active")
        self.assertEqual(dashboard["updates"]["apt_updates_available_count"], 2)
        self.assertEqual(dashboard["updates"]["firmware_updates_available_count"], 1)

    def test_failed_section_returns_unknown_without_crashing_dashboard(self) -> None:
        worker_manager = WorkerManager()
        health_manager = HealthManager(worker_manager)
        update_manager = UpdateManager()
        dashboard_manager = DashboardManager(
            health_manager=health_manager,
            update_manager=update_manager,
            worker_manager=worker_manager,
        )

        with patch.object(
            health_manager,
            "_hub_health",
            return_value={"status": "ok"},
        ), patch.object(
            health_manager,
            "_system_health",
            side_effect=RuntimeError,
        ), patch.object(
            health_manager,
            "_services_health",
            return_value={"seesam_hub": "active"},
        ), patch.object(
            update_manager,
            "get_update_status",
            return_value={"apt": {}, "firmware": {}},
        ), patch.object(
            worker_manager,
            "is_online",
            return_value=False,
        ):
            dashboard = dashboard_manager.get_dashboard()

        self.assertEqual(dashboard["hub"], {"status": "ok"})
        self.assertEqual(dashboard["system"], UNKNOWN)
        self.assertEqual(dashboard["worker"]["online"], False)

    def test_failed_updates_section_returns_unknown(self) -> None:
        worker_manager = WorkerManager()
        health_manager = HealthManager(worker_manager)
        update_manager = UpdateManager()
        dashboard_manager = DashboardManager(
            health_manager=health_manager,
            update_manager=update_manager,
            worker_manager=worker_manager,
        )

        with patch.object(
            health_manager,
            "_hub_health",
            return_value={"status": "ok"},
        ), patch.object(
            health_manager,
            "_system_health",
            return_value={"disk_usage_percent": 10.0},
        ), patch.object(
            health_manager,
            "_services_health",
            return_value={"seesam_hub": "active"},
        ), patch.object(
            worker_manager,
            "is_online",
            return_value=False,
        ), patch.object(
            update_manager,
            "get_update_status",
            side_effect=RuntimeError,
        ):
            dashboard = dashboard_manager.get_dashboard()

        self.assertEqual(dashboard["updates"], UNKNOWN)


if __name__ == "__main__":
    unittest.main()
