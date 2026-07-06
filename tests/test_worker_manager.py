import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services.worker_manager import WorkerManager, WorkerManagerError


class WorkerManagerTests(unittest.TestCase):
    def test_wake_sends_magic_packet(self) -> None:
        manager = WorkerManager(host="worker.local", user="marko", mac_address="aa:bb:cc")

        with patch("services.worker_manager.send_magic_packet") as send_magic_packet:
            manager.wake()

        send_magic_packet.assert_called_once_with("aa:bb:cc")
        self.assertIsNotNone(manager.last_used_at)

    def test_wait_until_online_marks_worker_used(self) -> None:
        manager = WorkerManager()

        with patch.object(manager, "is_online", return_value=True):
            online = manager.wait_until_online(timeout_seconds=1, poll_interval_seconds=0)

        self.assertTrue(online)
        self.assertIsNotNone(manager.last_used_at)

    def test_shutdown_raises_when_ssh_command_fails(self) -> None:
        manager = WorkerManager(host="worker.local", user="marko", mac_address="aa:bb:cc")
        result = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )

        with patch("services.worker_manager.logger"), patch(
            "services.worker_manager.run_ssh_command",
            return_value=result,
        ):
            with self.assertRaises(WorkerManagerError):
                manager.shutdown()

    def test_shutdown_marks_worker_used_on_success(self) -> None:
        manager = WorkerManager(host="worker.local", user="marko", mac_address="aa:bb:cc")
        result = subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

        with patch("services.worker_manager.run_ssh_command", return_value=result):
            manager.shutdown()

        self.assertIsNotNone(manager.last_used_at)

    def test_seconds_since_last_used_returns_none_before_first_use(self) -> None:
        manager = WorkerManager()

        self.assertIsNone(manager.seconds_since_last_used())
        self.assertFalse(manager.is_idle())

    def test_is_idle_returns_true_after_timeout(self) -> None:
        manager = WorkerManager(idle_timeout_seconds=60)
        manager.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=61)

        self.assertTrue(manager.is_idle())

    def test_shutdown_if_idle_returns_offline_without_shutdown(self) -> None:
        manager = WorkerManager()

        with patch.object(manager, "is_online", return_value=False), patch.object(
            manager,
            "shutdown",
        ) as shutdown:
            result = manager.shutdown_if_idle()

        self.assertEqual(result["status"], "offline")
        shutdown.assert_not_called()

    def test_shutdown_if_idle_does_not_shutdown_when_not_tracked(self) -> None:
        manager = WorkerManager()

        with patch.object(manager, "is_online", return_value=True), patch.object(
            manager,
            "shutdown",
        ) as shutdown:
            result = manager.shutdown_if_idle()

        self.assertEqual(result["status"], "not_tracked")
        shutdown.assert_not_called()

    def test_shutdown_if_idle_returns_remaining_seconds_when_active(self) -> None:
        manager = WorkerManager(idle_timeout_seconds=60)
        manager.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=20)

        with patch.object(manager, "is_online", return_value=True), patch.object(
            manager,
            "shutdown",
        ) as shutdown:
            result = manager.shutdown_if_idle()

        self.assertEqual(result["status"], "active")
        self.assertFalse(result["idle"])
        self.assertGreater(result["remaining_seconds"], 0)
        shutdown.assert_not_called()

    def test_shutdown_if_idle_shuts_down_when_idle(self) -> None:
        manager = WorkerManager(idle_timeout_seconds=60)
        manager.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=61)

        with patch.object(manager, "is_online", return_value=True), patch.object(
            manager,
            "shutdown",
        ) as shutdown:
            result = manager.shutdown_if_idle()

        self.assertEqual(result["status"], "shutdown_sent")
        self.assertTrue(result["idle"])
        shutdown.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
