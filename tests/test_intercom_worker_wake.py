import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import main


class IntercomWorkerWakeTests(unittest.TestCase):
    def test_worker_online_returns_already_online_without_waking_or_listening(self) -> None:
        listen_start = AsyncMock()
        with patch.object(
            main.worker_manager, "is_online", return_value=True
        ), patch.object(main.worker_manager, "wake") as wake, patch(
            "app.main._request_worker_listen", listen_start
        ):
            response = asyncio.run(self._post_wake())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "action": "worker_already_online"},
        )
        wake.assert_not_called()
        listen_start.assert_not_awaited()

    def test_worker_offline_sends_wake_without_starting_listening(self) -> None:
        listen_start = AsyncMock()
        with patch.object(
            main.worker_manager, "is_online", return_value=False
        ), patch.object(main.worker_manager, "wake") as wake, patch(
            "app.main._request_worker_listen", listen_start
        ):
            response = asyncio.run(self._post_wake())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "action": "worker_wake_sent"},
        )
        wake.assert_called_once_with()
        listen_start.assert_not_awaited()

    async def _post_wake(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/intercom/worker/wake")


if __name__ == "__main__":
    unittest.main()
