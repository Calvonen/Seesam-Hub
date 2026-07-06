import unittest

from services.intent_router import (
    UNKNOWN_INTENT,
    WORKER_MARK_USED,
    WORKER_SHUTDOWN,
    WORKER_STATUS,
    WORKER_WAKE,
    IntentRouter,
)


class IntentRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = IntentRouter()

    def test_detects_worker_wake(self) -> None:
        phrases = (
            "käynnistä worker",
            "herätä palvelin",
            "Herätä palvelin!",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.route(phrase), WORKER_WAKE)

    def test_detects_worker_shutdown(self) -> None:
        phrases = (
            "sammuta worker",
            "sammuta palvelin",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.route(phrase), WORKER_SHUTDOWN)

    def test_detects_worker_status(self) -> None:
        phrases = (
            "onko worker päällä",
            "palvelimen tila",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.route(phrase), WORKER_STATUS)

    def test_detects_worker_mark_used(self) -> None:
        self.assertEqual(
            self.router.route("merkkaa worker käytetyksi"),
            WORKER_MARK_USED,
        )

    def test_unknown_when_no_rule_matches(self) -> None:
        self.assertEqual(self.router.route("soita musiikkia"), UNKNOWN_INTENT)
        self.assertEqual(self.router.route(""), UNKNOWN_INTENT)


if __name__ == "__main__":
    unittest.main()
