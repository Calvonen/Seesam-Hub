import subprocess
import unittest
from unittest.mock import patch

from services.worker_manager import WorkerManager, WorkerManagerError


class WorkerManagerTests(unittest.TestCase):
    def test_wake_sends_magic_packet(self) -> None:
        manager = WorkerManager(host="worker.local", user="marko", mac_address="aa:bb:cc")

        with patch("services.worker_manager.send_magic_packet") as send_magic_packet:
            manager.wake()

        send_magic_packet.assert_called_once_with("aa:bb:cc")

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


if __name__ == "__main__":
    unittest.main()
