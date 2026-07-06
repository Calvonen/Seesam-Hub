import logging
import re

logger = logging.getLogger(__name__)

IntentName = str

UNKNOWN_INTENT = "unknown"
WORKER_WAKE = "worker_wake"
WORKER_SHUTDOWN = "worker_shutdown"
WORKER_STATUS = "worker_status"
WORKER_MARK_USED = "worker_mark_used"


class IntentRouter:
    def route(self, text: str) -> IntentName:
        normalized_text = self._normalize(text)
        logger.debug("Routing intent", extra={"text": normalized_text})

        if not normalized_text:
            return UNKNOWN_INTENT

        if self._matches_worker_mark_used(normalized_text):
            return WORKER_MARK_USED

        if self._matches_worker_status(normalized_text):
            return WORKER_STATUS

        if self._matches_worker_shutdown(normalized_text):
            return WORKER_SHUTDOWN

        if self._matches_worker_wake(normalized_text):
            return WORKER_WAKE

        return UNKNOWN_INTENT

    def _normalize(self, text: str) -> str:
        lowered = text.strip().casefold()
        without_punctuation = re.sub(r"[^\w\såäö]", " ", lowered)
        return re.sub(r"\s+", " ", without_punctuation).strip()

    def _has_worker_target(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in (
                "worker",
                "palvelin",
                "palvelimen",
                "palvelinta",
                "tyokone",
                "työkone",
            )
        )

    def _matches_worker_wake(self, text: str) -> bool:
        wake_keywords = ("käynnistä", "kaynnista", "herätä", "herata")
        return self._has_worker_target(text) and any(keyword in text for keyword in wake_keywords)

    def _matches_worker_shutdown(self, text: str) -> bool:
        shutdown_keywords = ("sammuta", "sulje", "poweroff")
        return self._has_worker_target(text) and any(
            keyword in text for keyword in shutdown_keywords
        )

    def _matches_worker_status(self, text: str) -> bool:
        status_keywords = ("tila", "päällä", "paalla", "online", "status")
        question_keywords = ("onko", "näytä", "nayta", "kerro")
        return self._has_worker_target(text) and (
            any(keyword in text for keyword in status_keywords)
            or any(keyword in text for keyword in question_keywords)
        )

    def _matches_worker_mark_used(self, text: str) -> bool:
        usage_keywords = (
            "käytetyksi",
            "kaytetyksi",
            "käytetty",
            "kaytetty",
            "used",
        )
        mark_keywords = ("merkkaa", "merkitse", "mark")
        return (
            self._has_worker_target(text)
            and any(keyword in text for keyword in mark_keywords)
            and any(keyword in text for keyword in usage_keywords)
        )
