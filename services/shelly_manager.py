import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class ShellyManager:
    def __init__(
        self,
        base_url: str = settings.SPEAKER_SHELLY_BASE_URL,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def turn_speaker_power_on(self) -> dict[str, object]:
        return self._set_speaker_power(on=True)

    def turn_speaker_power_off(self) -> dict[str, object]:
        return self._set_speaker_power(on=False)

    def get_speaker_power_status(self) -> dict[str, object]:
        response = self._request("GET", "/rpc/Switch.GetStatus", params={"id": "0"})
        if not response["ok"]:
            return response

        data = response["data"]
        if not isinstance(data, dict):
            return self._error("speaker Shelly returned an invalid status payload")

        return {
            "ok": True,
            "status": "speaker_status",
            "on": data.get("output"),
            "data": data,
        }

    def _set_speaker_power(self, *, on: bool) -> dict[str, object]:
        response = self._request(
            "GET",
            "/rpc/Switch.Set",
            params={"id": "0", "on": str(on).lower()},
        )
        if not response["ok"]:
            return response

        return {
            "ok": True,
            "status": "speaker_power_on" if on else "speaker_power_off",
            "on": on,
            "data": response["data"],
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str],
    ) -> dict[str, object]:
        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.request(method, url, params=params)
                response.raise_for_status()
                return {"ok": True, "data": response.json()}
        except httpx.RequestError as exc:
            logger.warning(
                "Speaker Shelly did not respond",
                extra={"shelly_url": url, "error": str(exc)},
            )
            return self._error("speaker Shelly did not respond", detail=str(exc))
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Speaker Shelly returned an error",
                extra={
                    "shelly_url": url,
                    "status_code": exc.response.status_code,
                    "error": str(exc),
                },
            )
            return self._error(
                f"speaker Shelly returned HTTP {exc.response.status_code}",
                detail=exc.response.text,
            )
        except ValueError as exc:
            logger.warning(
                "Speaker Shelly returned invalid JSON",
                extra={"shelly_url": url, "error": str(exc)},
            )
            return self._error("speaker Shelly returned invalid JSON", detail=str(exc))

    def _error(self, message: str, *, detail: str | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": False,
            "status": "speaker_shelly_error",
            "error": message,
        }
        if detail:
            result["detail"] = detail
        return result
