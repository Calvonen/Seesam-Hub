import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import main


class IntercomWorkerShutdownTests(unittest.TestCase):
    def test_worker_offline_returns_already_offline_without_shutdown(self) -> None:
        listen_request = AsyncMock()
        worker_request = AsyncMock()
        with patch.object(
            main.worker_manager, "is_online", return_value=False
        ), patch.object(main.worker_manager, "shutdown") as shutdown, patch(
            "app.main._request_worker_listen", listen_request
        ), patch(
            "app.main._proxy_worker_request", worker_request
        ):
            response = asyncio.run(self._post_shutdown())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "action": "worker_already_offline"},
        )
        shutdown.assert_not_called()
        worker_request.assert_not_awaited()
        listen_request.assert_not_awaited()

    def test_worker_online_sends_shutdown_without_starting_listening(self) -> None:
        listen_request = AsyncMock()
        worker_request = AsyncMock(return_value=main.Response(status_code=200))
        with patch.object(
            main.worker_manager, "is_online", return_value=True
        ), patch.object(main.worker_manager, "shutdown") as shutdown, patch(
            "app.main._request_worker_listen", listen_request
        ), patch(
            "app.main._proxy_worker_request", worker_request
        ):
            response = asyncio.run(self._post_shutdown())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "action": "worker_shutdown_sent"},
        )
        worker_request.assert_awaited_once_with("/system/shutdown")
        shutdown.assert_not_called()
        listen_request.assert_not_awaited()

    async def _post_shutdown(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/intercom/worker/shutdown")


if __name__ == "__main__":
    unittest.main()
