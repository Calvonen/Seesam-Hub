from datetime import datetime
import socket

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.intent_router import (
    UNKNOWN_INTENT,
    WORKER_MARK_USED,
    WORKER_SHUTDOWN,
    WORKER_STATUS,
    WORKER_WAKE,
    IntentRouter,
)
from services.health_manager import HealthManager
from services.dashboard_manager import DashboardManager
from services.worker_manager import WorkerManager, WorkerManagerError
from services.update_manager import UpdateManager

app = FastAPI(title="Seesam Hub")
worker_manager = WorkerManager()
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


def _run_intent_action(intent: str) -> dict[str, object]:
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
