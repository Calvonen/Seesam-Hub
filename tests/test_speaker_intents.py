import unittest
from unittest.mock import Mock, patch

from app import main
from services.intent_router import (
    SPEAKER_POWER_OFF,
    SPEAKER_POWER_ON,
    SPEAKER_STATUS,
)


class SpeakerIntentActionTests(unittest.TestCase):
    def test_speaker_routes_are_registered(self) -> None:
        routes = {
            (route.path, method)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertIn(("/speakers/power-on", "POST"), routes)
        self.assertIn(("/speakers/power-off", "POST"), routes)
        self.assertIn(("/speakers/status", "GET"), routes)

    def test_speaker_power_on_intent_turns_shelly_on(self) -> None:
        shelly_manager = Mock()
        shelly_manager.turn_speaker_power_on.return_value = {
            "ok": True,
            "status": "speaker_power_on",
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main._run_intent_action(SPEAKER_POWER_ON)

        self.assertEqual(result["status"], "speaker_power_on")
        shelly_manager.turn_speaker_power_on.assert_called_once_with()

    def test_speaker_power_on_endpoint_turns_shelly_on(self) -> None:
        shelly_manager = Mock()
        shelly_manager.turn_speaker_power_on.return_value = {
            "ok": True,
            "status": "speaker_power_on",
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main.turn_speaker_power_on()

        self.assertEqual(result["status"], "speaker_power_on")
        shelly_manager.turn_speaker_power_on.assert_called_once_with()

    def test_speaker_power_off_intent_turns_shelly_off(self) -> None:
        shelly_manager = Mock()
        shelly_manager.turn_speaker_power_off.return_value = {
            "ok": True,
            "status": "speaker_power_off",
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main._run_intent_action(SPEAKER_POWER_OFF)

        self.assertEqual(result["status"], "speaker_power_off")
        shelly_manager.turn_speaker_power_off.assert_called_once_with()

    def test_speaker_power_off_endpoint_turns_shelly_off(self) -> None:
        shelly_manager = Mock()
        shelly_manager.turn_speaker_power_off.return_value = {
            "ok": True,
            "status": "speaker_power_off",
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main.turn_speaker_power_off()

        self.assertEqual(result["status"], "speaker_power_off")
        shelly_manager.turn_speaker_power_off.assert_called_once_with()

    def test_speaker_power_status_intent_reads_shelly_status(self) -> None:
        shelly_manager = Mock()
        shelly_manager.get_speaker_power_status.return_value = {
            "ok": True,
            "status": "speaker_status",
            "on": True,
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main._run_intent_action(SPEAKER_STATUS)

        self.assertEqual(result["status"], "speaker_status")
        self.assertEqual(result["on"], True)
        shelly_manager.get_speaker_power_status.assert_called_once_with()

    def test_speaker_status_endpoint_reads_shelly_status(self) -> None:
        shelly_manager = Mock()
        shelly_manager.get_speaker_power_status.return_value = {
            "ok": True,
            "status": "speaker_status",
            "on": True,
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            result = main.get_speaker_status()

        self.assertEqual(result["status"], "speaker_status")
        self.assertEqual(result["on"], True)
        shelly_manager.get_speaker_power_status.assert_called_once_with()

    def test_speaker_endpoint_returns_502_when_shelly_fails(self) -> None:
        shelly_manager = Mock()
        shelly_manager.turn_speaker_power_on.return_value = {
            "ok": False,
            "status": "speaker_shelly_error",
            "error": "speaker Shelly did not respond",
        }

        with patch.object(main, "speaker_shelly_manager", shelly_manager):
            with self.assertRaises(main.HTTPException) as exc:
                main.turn_speaker_power_on()

        self.assertEqual(exc.exception.status_code, 502)
        self.assertEqual(exc.exception.detail["error"], "speaker Shelly did not respond")


if __name__ == "__main__":
    unittest.main()
