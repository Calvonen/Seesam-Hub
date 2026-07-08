import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import main

ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient


class FakeWorkerAsyncClient:
    response = httpx.Response(200, json={"ok": True})
    request_url: str | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "FakeWorkerAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        type(self).request_url = url
        return type(self).response


class IntercomButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        main.worker_manager.host = "worker.local"
        main.worker_manager.last_used_at = None
        FakeWorkerAsyncClient.response = httpx.Response(200, json={"ok": True})
        FakeWorkerAsyncClient.request_url = None

    def test_worker_online_requests_listen_start(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=True), patch.object(
            main.worker_manager,
            "wake",
        ) as wake, patch(
            "app.main.httpx.AsyncClient",
            FakeWorkerAsyncClient,
        ):
            response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "intercom")
        self.assertEqual(payload["action"], "listen_start_requested")
        self.assertEqual(payload["worker_host"], "worker.local")
        self.assertTrue(payload["worker_online"])
        self.assertIsNotNone(payload["last_used_at"])
        self.assertIsNotNone(main.worker_manager.last_used_at)
        self.assertEqual(
            payload["last_used_at"],
            main.worker_manager.last_used_at.isoformat(),
        )
        self.assertEqual(
            FakeWorkerAsyncClient.request_url,
            "http://worker.local:8000/listen/start",
        )
        wake.assert_not_called()

    def test_worker_offline_sends_wake(self) -> None:
        listen_start = AsyncMock(return_value=True)
        with patch.object(main.worker_manager, "is_online", return_value=False), patch.object(
            main.worker_manager,
            "wake",
        ) as wake, patch(
            "app.main._request_worker_listen_start",
            listen_start,
        ):
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
        listen_start.assert_not_awaited()

    def test_worker_listen_start_error_returns_502(self) -> None:
        listen_start = AsyncMock(return_value=False)
        with patch.object(main.worker_manager, "is_online", return_value=True), patch.object(
            main.worker_manager,
            "wake",
        ) as wake, patch(
            "app.main._request_worker_listen_start",
            listen_start,
        ):
            response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "worker listen start failed")
        self.assertIsNone(main.worker_manager.last_used_at)
        listen_start.assert_awaited_once_with()
        wake.assert_not_called()

    async def _post_button_press(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with ORIGINAL_ASYNC_CLIENT(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/intercom/button")


if __name__ == "__main__":
    unittest.main()
