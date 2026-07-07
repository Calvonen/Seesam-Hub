import unittest

import httpx

from services.shelly_manager import ShellyManager


class ShellyManagerTests(unittest.TestCase):
    def test_turn_speaker_power_on_calls_shelly_switch_set(self) -> None:
        seen_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append(request)
            return httpx.Response(200, json={"was_on": False})

        manager = ShellyManager(
            base_url="http://shelly.local",
            transport=httpx.MockTransport(handler),
        )

        result = manager.turn_speaker_power_on()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "speaker_power_on")
        self.assertEqual(result["on"], True)
        self.assertEqual(seen_requests[0].method, "GET")
        self.assertEqual(seen_requests[0].url.path, "/rpc/Switch.Set")
        self.assertEqual(seen_requests[0].url.params["id"], "0")
        self.assertEqual(seen_requests[0].url.params["on"], "true")

    def test_turn_speaker_power_off_calls_shelly_switch_set(self) -> None:
        seen_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append(request)
            return httpx.Response(200, json={"was_on": True})

        manager = ShellyManager(
            base_url="http://shelly.local",
            transport=httpx.MockTransport(handler),
        )

        result = manager.turn_speaker_power_off()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "speaker_power_off")
        self.assertEqual(result["on"], False)
        self.assertEqual(seen_requests[0].method, "GET")
        self.assertEqual(seen_requests[0].url.path, "/rpc/Switch.Set")
        self.assertEqual(seen_requests[0].url.params["id"], "0")
        self.assertEqual(seen_requests[0].url.params["on"], "false")

    def test_get_speaker_power_status_calls_shelly_get_status(self) -> None:
        seen_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append(request)
            return httpx.Response(200, json={"id": 0, "output": True})

        manager = ShellyManager(
            base_url="http://shelly.local",
            transport=httpx.MockTransport(handler),
        )

        result = manager.get_speaker_power_status()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "speaker_status")
        self.assertEqual(result["on"], True)
        self.assertEqual(seen_requests[0].method, "GET")
        self.assertEqual(seen_requests[0].url.path, "/rpc/Switch.GetStatus")
        self.assertEqual(seen_requests[0].url.params["id"], "0")

    def test_returns_clear_error_when_shelly_does_not_respond(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        manager = ShellyManager(
            base_url="http://shelly.local",
            transport=httpx.MockTransport(handler),
        )

        result = manager.turn_speaker_power_on()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "speaker_shelly_error")
        self.assertEqual(result["error"], "speaker Shelly did not respond")

    def test_returns_clear_error_when_shelly_returns_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        manager = ShellyManager(
            base_url="http://shelly.local",
            transport=httpx.MockTransport(handler),
        )

        result = manager.turn_speaker_power_on()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "speaker_shelly_error")
        self.assertEqual(result["error"], "speaker Shelly returned HTTP 500")


if __name__ == "__main__":
    unittest.main()
