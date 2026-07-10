from datetime import datetime
import socket
from collections.abc import Mapping

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from services.intent_router import (
    SPEAKER_POWER_OFF,
    SPEAKER_POWER_ON,
    SPEAKER_STATUS,
    UNKNOWN_INTENT,
    WORKER_MARK_USED,
    WORKER_SHUTDOWN,
    WORKER_STATUS,
    WORKER_WAKE,
    IntentRouter,
)
from services.health_manager import HealthManager
from services.dashboard_manager import DashboardManager
from services.shelly_manager import ShellyManager
from services.worker_manager import WorkerManager, WorkerManagerError
from services.update_manager import UpdateManager

app = FastAPI(title="Seesam Hub")
worker_manager = WorkerManager()
speaker_shelly_manager = ShellyManager()
intent_router = IntentRouter()
health_manager = HealthManager(worker_manager)
update_manager = UpdateManager()
dashboard_manager = DashboardManager(
    health_manager=health_manager,
    update_manager=update_manager,
    worker_manager=worker_manager,
)


class IntentRequest(BaseModel):
    text: str


WORKER_API_PORT = 8000
WORKER_PROXY_TIMEOUT_SECONDS = 60.0
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Seesam Hub",
        "status": "running",
        "host": socket.gethostname(),
        "time": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/status")
def status() -> dict[str, object]:
    worker_online = worker_manager.is_online()
    return {
        "hub": {
            "status": "ok",
            "host": socket.gethostname(),
            "time": datetime.now().isoformat(timespec="seconds"),
        },
        "worker": {
            "host": worker_manager.host,
            "online": worker_online,
            "last_used_at": (
                worker_manager.last_used_at.isoformat()
                if worker_manager.last_used_at
                else None
            ),
            "idle_timeout_seconds": worker_manager.idle_timeout_seconds,
        },
    }


@app.get("/health")
def health() -> dict[str, object]:
    return health_manager.get_health()


@app.get("/updates")
def updates() -> dict[str, object]:
    return update_manager.get_update_status()


@app.get("/dashboard")
def dashboard() -> dict[str, object]:
    return dashboard_manager.get_dashboard()


@app.post("/worker/wake")
def wake_worker() -> dict[str, str]:
    try:
        worker_manager.wake()
    except WorkerManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "wake_sent"}


@app.post("/worker/wait-online")
def wait_worker_online() -> dict[str, object]:
    online = worker_manager.wait_until_online()
    if not online:
        raise HTTPException(status_code=504, detail="worker did not become online in time")

    return {"status": "online", "online": True}


@app.post("/worker/shutdown")
def shutdown_worker() -> dict[str, str]:
    try:
        worker_manager.shutdown()
    except WorkerManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "shutdown_sent"}


@app.post("/worker/used")
def mark_worker_used() -> dict[str, object]:
    worker_manager.mark_used()
    return {
        "status": "marked_used",
        "last_used_at": (
            worker_manager.last_used_at.isoformat()
            if worker_manager.last_used_at
            else None
        ),
    }


@app.post("/intercom/button")
async def intercom_button_pressed() -> dict[str, object]:
    result = await _start_intercom_listening()

    if result["worker_online"]:
        action = "listen_start_requested"
    else:
        action = result["action"]

    return {
        "ok": True,
        "source": "intercom",
        "action": action,
        "worker_host": worker_manager.host,
        "worker_online": result["worker_online"],
        "last_used_at": (
            worker_manager.last_used_at.isoformat()
            if worker_manager.last_used_at
            else None
        ),
    }


@app.post("/intercom/listen/start")
async def start_intercom_listening() -> dict[str, object]:
    return await _start_intercom_listening()


@app.post("/intercom/listen/stop")
async def stop_intercom_listening() -> dict[str, object]:
    if not worker_manager.is_online():
        raise HTTPException(status_code=503, detail="worker_offline")

    result = await _request_worker_listen("POST", "/listen/stop")
    worker_manager.mark_used()
    return {**result, "worker_online": True}


@app.get("/intercom/listen/status")
async def get_intercom_listening_status() -> dict[str, object]:
    if not worker_manager.is_online():
        return {"worker_online": False}

    result = await _request_worker_listen("GET", "/listen/status")
    return {**result, "worker_online": True}


@app.get("/intercom/listen/last-audio")
async def get_intercom_last_audio() -> Response:
    if not worker_manager.is_online():
        raise HTTPException(status_code=503, detail="worker_offline")

    try:
        async with httpx.AsyncClient(timeout=WORKER_PROXY_TIMEOUT_SECONDS) as client:
            worker_response = await client.get(_worker_api_url("/listen/last-audio"))
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="worker did not respond") from exc

    if worker_response.status_code == 404:
        return Response(status_code=404)
    if not worker_response.is_success:
        raise HTTPException(status_code=502, detail="worker audio request failed")

    return Response(content=worker_response.content, media_type="audio/wav")


@app.post("/intercom/listen/upload")
async def upload_intercom_audio(request: Request) -> Response:
    if not worker_manager.is_online():
        raise HTTPException(status_code=503, detail="worker_offline")

    body = await request.body()
    content_type = request.headers.get("content-type")
    headers = {"content-type": content_type} if content_type else None

    try:
        async with httpx.AsyncClient(timeout=WORKER_PROXY_TIMEOUT_SECONDS) as client:
            worker_response = await client.post(
                _worker_api_url("/listen/upload"),
                content=body,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="worker did not respond") from exc

    worker_manager.mark_used()
    return Response(
        content=worker_response.content,
        status_code=worker_response.status_code,
        headers=_response_headers(worker_response.headers),
    )


async def _start_intercom_listening() -> dict[str, object]:
    if worker_manager.is_online():
        result = await _request_worker_listen("POST", "/listen/start")
        worker_manager.mark_used()
        return {**result, "worker_online": True}

    worker_manager.mark_used()
    try:
        worker_manager.wake()
    except WorkerManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"action": "wake_sent", "worker_online": False}


async def _request_worker_listen(method: str, endpoint: str) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=WORKER_PROXY_TIMEOUT_SECONDS) as client:
            if method == "GET":
                worker_response = await client.get(_worker_api_url(endpoint))
            else:
                worker_response = await client.post(_worker_api_url(endpoint))
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="worker did not respond") from exc

    if not worker_response.is_success:
        raise HTTPException(status_code=502, detail="worker listen request failed")

    result = worker_response.json()
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="invalid worker response")
    return result


@app.get("/worker/idle")
def worker_idle() -> dict[str, object]:
    seconds_since_last_used = worker_manager.seconds_since_last_used()
    remaining_seconds = (
        max(0, worker_manager.idle_timeout_seconds - seconds_since_last_used)
        if seconds_since_last_used is not None
        else None
    )

    return {
        "online": worker_manager.is_online(),
        "idle": worker_manager.is_idle(),
        "last_used_at": (
            worker_manager.last_used_at.isoformat()
            if worker_manager.last_used_at
            else None
        ),
        "seconds_since_last_used": seconds_since_last_used,
        "remaining_seconds": remaining_seconds,
        "idle_timeout_seconds": worker_manager.idle_timeout_seconds,
    }


@app.post("/worker/shutdown-if-idle")
def shutdown_worker_if_idle() -> dict[str, object]:
    try:
        return worker_manager.shutdown_if_idle()
    except WorkerManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/speakers/power-on")
def turn_speaker_power_on() -> dict[str, object]:
    return _shelly_response_or_502(speaker_shelly_manager.turn_speaker_power_on())


@app.post("/speakers/power-off")
def turn_speaker_power_off() -> dict[str, object]:
    return _shelly_response_or_502(speaker_shelly_manager.turn_speaker_power_off())


@app.get("/speakers/status")
def get_speaker_status() -> dict[str, object]:
    return _shelly_response_or_502(speaker_shelly_manager.get_speaker_power_status())


@app.post("/intent")
def route_intent(request: IntentRequest) -> dict[str, object]:
    intent = intent_router.route(request.text)

    try:
        action_result = _run_intent_action(intent)
    except WorkerManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "intent": intent,
        "action_result": action_result,
    }


@app.post("/chat")
async def proxy_chat(request: Request) -> Response:
    payload = await request.json()
    return await _proxy_worker_json("/chat", payload)


@app.post("/speak")
async def proxy_speak(request: Request) -> Response:
    payload = await request.json()
    return await _proxy_worker_json("/speak", payload)


@app.post("/transcribe")
async def proxy_transcribe(request: Request) -> Response:
    body = await request.body()
    content_type = request.headers.get("content-type")
    headers = {"content-type": content_type} if content_type else None
    return await _proxy_worker_request("/transcribe", content=body, headers=headers)


async def _proxy_worker_json(endpoint: str, payload: object) -> Response:
    return await _proxy_worker_request(endpoint, json=payload)


async def _proxy_worker_request(
    endpoint: str,
    *,
    json: object | None = None,
    content: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    try:
        async with httpx.AsyncClient(timeout=WORKER_PROXY_TIMEOUT_SECONDS) as client:
            worker_response = await client.post(
                _worker_api_url(endpoint),
                json=json,
                content=content,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="worker did not respond") from exc

    if worker_response.is_success:
        worker_manager.mark_used()

    return Response(
        content=worker_response.content,
        status_code=worker_response.status_code,
        headers=_response_headers(worker_response.headers),
    )


def _worker_api_url(endpoint: str) -> str:
    return f"http://{worker_manager.host}:{WORKER_API_PORT}{endpoint}"


def _response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length"
    }


def _run_intent_action(intent: str) -> dict[str, object]:
    if intent == SPEAKER_POWER_ON:
        return _shelly_response_or_502(speaker_shelly_manager.turn_speaker_power_on())

    if intent == SPEAKER_POWER_OFF:
        return _shelly_response_or_502(speaker_shelly_manager.turn_speaker_power_off())

    if intent == SPEAKER_STATUS:
        return _shelly_response_or_502(speaker_shelly_manager.get_speaker_power_status())

    if intent == WORKER_WAKE:
        worker_manager.wake()
        return {"status": "wake_sent"}

    if intent == WORKER_SHUTDOWN:
        worker_manager.shutdown()
        return {"status": "shutdown_sent"}

    if intent == WORKER_STATUS:
        return {
            "host": worker_manager.host,
            "online": worker_manager.is_online(),
            "last_used_at": (
                worker_manager.last_used_at.isoformat()
                if worker_manager.last_used_at
                else None
            ),
            "idle_timeout_seconds": worker_manager.idle_timeout_seconds,
        }

    if intent == WORKER_MARK_USED:
        worker_manager.mark_used()
        return {
            "status": "marked_used",
            "last_used_at": (
                worker_manager.last_used_at.isoformat()
                if worker_manager.last_used_at
                else None
            ),
        }

    if intent == UNKNOWN_INTENT:
        return {"status": "unknown_intent"}

    return {"status": "unsupported_intent"}


def _shelly_response_or_502(result: dict[str, object]) -> dict[str, object]:
    if result.get("ok") is False:
        raise HTTPException(status_code=502, detail=result)

    return result
