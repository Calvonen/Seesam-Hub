import asyncio
import unittest
from unittest.mock import patch

import httpx

from app import main


class FakeAsyncClient:
    response = httpx.Response(200, json={"ok": True})
    request_kwargs: dict[str, object] | None = None
    request_url: str | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        type(self).request_url = url
        type(self).request_kwargs = kwargs
        return type(self).response


class WorkerProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        main.worker_manager.host = "worker.local"
        main.worker_manager.last_used_at = None
        FakeAsyncClient.response = httpx.Response(200, json={"ok": True})
        FakeAsyncClient.request_kwargs = None
        FakeAsyncClient.request_url = None

    def test_proxy_routes_are_registered(self) -> None:
        routes = {
            (route.path, method)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertIn(("/chat", "POST"), routes)
        self.assertIn(("/speak", "POST"), routes)
        self.assertIn(("/transcribe", "POST"), routes)

    def test_chat_proxies_json_to_worker_and_marks_used(self) -> None:
        with patch("app.main.httpx.AsyncClient", FakeAsyncClient):
            response = asyncio.run(main._proxy_worker_json("/chat", {"message": "hei"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{"ok":true}')
        self.assertEqual(FakeAsyncClient.request_url, "http://worker.local:8000/chat")
        self.assertEqual(FakeAsyncClient.request_kwargs["json"], {"message": "hei"})
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_speak_preserves_worker_audio_response(self) -> None:
        FakeAsyncClient.response = httpx.Response(
            200,
            content=b"RIFF audio",
            headers={"content-type": "audio/wav"},
        )

        with patch("app.main.httpx.AsyncClient", FakeAsyncClient):
            response = asyncio.run(main._proxy_worker_json("/speak", {"text": "hei"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"RIFF audio")
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(FakeAsyncClient.request_url, "http://worker.local:8000/speak")
        self.assertEqual(FakeAsyncClient.request_kwargs["json"], {"text": "hei"})
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_transcribe_forwards_multipart_body_and_content_type(self) -> None:
        with patch("app.main.httpx.AsyncClient", FakeAsyncClient):
            response = asyncio.run(
                main._proxy_worker_request(
                    "/transcribe",
                    content=b'--abc\r\ncontent-disposition: form-data; name="file"\r\n\r\naudio',
                    headers={"content-type": "multipart/form-data; boundary=abc"},
                )
            )

        headers = FakeAsyncClient.request_kwargs["headers"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeAsyncClient.request_url, "http://worker.local:8000/transcribe")
        self.assertIn(b'name="file"', FakeAsyncClient.request_kwargs["content"])
        self.assertTrue(headers["content-type"].startswith("multipart/form-data"))
        self.assertIsNotNone(main.worker_manager.last_used_at)

    def test_worker_request_error_returns_502(self) -> None:
        class FailingAsyncClient(FakeAsyncClient):
            async def post(self, url: str, **kwargs: object) -> httpx.Response:
                request = httpx.Request("POST", url)
                raise httpx.ConnectError("connection failed", request=request)

        with patch("app.main.httpx.AsyncClient", FailingAsyncClient):
            with self.assertRaises(main.HTTPException) as exc:
                asyncio.run(main._proxy_worker_json("/chat", {"message": "hei"}))

        self.assertEqual(exc.exception.status_code, 502)
        self.assertIsNone(main.worker_manager.last_used_at)


if __name__ == "__main__":
    unittest.main()
