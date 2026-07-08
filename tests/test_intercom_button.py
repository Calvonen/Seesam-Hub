import asyncio
import unittest

import httpx

from app import main


class IntercomButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        main.worker_manager.host = "worker.local"
        main.worker_manager.last_used_at = None

    def test_button_press_marks_worker_used(self) -> None:
        response = asyncio.run(self._post_button_press())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "intercom")
        self.assertEqual(payload["action"], "button_pressed")
        self.assertEqual(payload["worker_host"], "worker.local")
        self.assertIsNotNone(payload["last_used_at"])
        self.assertIsNotNone(main.worker_manager.last_used_at)
        self.assertEqual(
            payload["last_used_at"],
            main.worker_manager.last_used_at.isoformat(),
        )

    async def _post_button_press(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/intercom/button")


if __name__ == "__main__":
    unittest.main()
