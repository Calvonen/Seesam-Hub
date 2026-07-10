import asyncio
import unittest
from unittest.mock import patch

import httpx

from app import main

ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient


class FakeWorkerAsyncClient:
    response = httpx.Response(200, json={"action": "listening_started"})
    request_method: str | None = None
    request_url: str | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "FakeWorkerAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str) -> httpx.Response:
        type(self).request_method = "POST"
        type(self).request_url = url
        return type(self).response

    async def get(self, url: str) -> httpx.Response:
        type(self).request_method = "GET"
        type(self).request_url = url
        return type(self).response


class IntercomListenTests(unittest.TestCase):
    def setUp(self) -> None:
        main.worker_manager.host = "worker.local"
        main.worker_manager.last_used_at = None
        FakeWorkerAsyncClient.response = httpx.Response(
            200, json={"action": "listening_started"}
        )
        FakeWorkerAsyncClient.request_method = None
        FakeWorkerAsyncClient.request_url = None

    def test_start_worker_online(self) -> None:
        response = self._request_with_worker_online("POST", "/intercom/listen/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "listening_started")
        self.assertTrue(response.json()["worker_online"])
        self.assertEqual(FakeWorkerAsyncClient.request_method, "POST")
        self.assertEqual(FakeWorkerAsyncClient.request_url, "http://worker.local:8000/listen/start")
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_start_worker_offline_wakes_worker(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=False), patch.object(
            main.worker_manager, "wake"
        ) as wake:
            response = asyncio.run(self._request("POST", "/intercom/listen/start"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"action": "wake_sent", "worker_online": False})
        wake.assert_called_once_with()
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_stop_worker_online(self) -> None:
        FakeWorkerAsyncClient.response = httpx.Response(
            200, json={"action": "listen_stopped_processing"}
        )
        response = self._request_with_worker_online("POST", "/intercom/listen/stop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "listen_stopped_processing")
        self.assertEqual(FakeWorkerAsyncClient.request_url, "http://worker.local:8000/listen/stop")
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_stop_worker_offline_returns_503(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=False):
            response = asyncio.run(self._request("POST", "/intercom/listen/stop"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "worker_offline")

    def test_status_worker_online(self) -> None:
        FakeWorkerAsyncClient.response = httpx.Response(
            200, json={"listening": True, "state": "recording"}
        )
        response = self._request_with_worker_online("GET", "/intercom/listen/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"listening": True, "state": "recording", "worker_online": True})
        self.assertEqual(FakeWorkerAsyncClient.request_method, "GET")
        self.assertEqual(FakeWorkerAsyncClient.request_url, "http://worker.local:8000/listen/status")

    def test_status_worker_offline(self) -> None:
        with patch.object(main.worker_manager, "is_online", return_value=False):
            response = asyncio.run(self._request("GET", "/intercom/listen/status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"worker_online": False})

    def _request_with_worker_online(self, method: str, path: str) -> httpx.Response:
        with patch.object(main.worker_manager, "is_online", return_value=True), patch(
            "app.main.httpx.AsyncClient", FakeWorkerAsyncClient
        ):
            return asyncio.run(self._request(method, path))

    async def _request(self, method: str, path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with ORIGINAL_ASYNC_CLIENT(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path)


if __name__ == "__main__":
    unittest.main()
