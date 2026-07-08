import asyncio
import unittest
from unittest.mock import patch

import httpx

from app import main
from services.worker_manager import WorkerManagerError


class IntercomButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        main.worker_manager.host = "worker.local"
        main.worker_manager.last_used_at = None

    def test_worker_online_returns_worker_ready(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=True), patch.object(
            main.worker_manager,
            "wake",
        ) as wake:
            response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "intercom")
        self.assertEqual(payload["action"], "worker_ready")
        self.assertEqual(payload["worker_host"], "worker.local")
        self.assertTrue(payload["worker_online"])
        self.assertIsNotNone(payload["last_used_at"])
        self.assertIsNotNone(main.worker_manager.last_used_at)
        self.assertEqual(
            payload["last_used_at"],
            main.worker_manager.last_used_at.isoformat(),
        )
        wake.assert_not_called()

    def test_worker_offline_sends_wake(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=False), patch.object(
            main.worker_manager,
            "wake",
        ) as wake:
            response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "intercom")
        self.assertEqual(payload["action"], "wake_sent")
        self.assertEqual(payload["worker_host"], "worker.local")
        self.assertFalse(payload["worker_online"])
        self.assertIsNotNone(payload["last_used_at"])
        self.assertIsNotNone(main.worker_manager.last_used_at)
        wake.assert_called_once_with()

    def test_wake_error_returns_http_error(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=False), patch.object(
            main.worker_manager,
            "wake",
            side_effect=WorkerManagerError("wake failed"),
        ):
            response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "wake failed")
        self.assertIsNotNone(main.worker_manager.last_used_at)

    async def _post_button_press(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/intercom/button")


if __name__ == "__main__":
    unittest.main()
