import logging
import socket
import time
from datetime import datetime, timezone

from config import settings
from drivers.ssh import run_ssh_command
from drivers.wakeonlan import send_magic_packet

logger = logging.getLogger(__name__)


class WorkerManagerError(RuntimeError):
    """Raised when worker management fails."""


class WorkerManager:
    def __init__(
        self,
        host: str = settings.WORKER_HOST,
        user: str = settings.WORKER_USER,
        mac_address: str = settings.WORKER_MAC,
        idle_timeout_seconds: int = settings.WORKER_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host
        self.user = user
        self.mac_address = mac_address
        self.idle_timeout_seconds = idle_timeout_seconds
        self.last_used_at: datetime | None = None

    def is_online(self, timeout_seconds: float = 2.0) -> bool:
        """Return True when the worker's SSH port accepts a TCP connection."""
        try:
            with socket.create_connection((self.host, 22), timeout=timeout_seconds):
                logger.debug("Worker SSH port is reachable", extra={"worker_host": self.host})
                return True
        except OSError as exc:
            logger.debug(
                "Worker SSH port is not reachable",
                extra={"worker_host": self.host, "error": str(exc)},
            )
            return False

    def wake(self) -> None:
        logger.info("Wake requested for worker", extra={"worker_host": self.host})
        try:
            send_magic_packet(self.mac_address)
        except RuntimeError as exc:
            raise WorkerManagerError(str(exc)) from exc
        self.mark_used()

    def wait_until_online(
        self,
        timeout_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
    ) -> bool:
        logger.info(
            "Waiting until worker is online",
            extra={"worker_host": self.host, "timeout_seconds": timeout_seconds},
        )

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.is_online():
                self.mark_used()
                logger.info("Worker is online", extra={"worker_host": self.host})
                return True
            time.sleep(poll_interval_seconds)

        logger.warning("Timed out waiting for worker", extra={"worker_host": self.host})
        return False

    def shutdown(self) -> None:
        logger.info("Shutdown requested for worker", extra={"worker_host": self.host})
        result = run_ssh_command(
            host=self.host,
            user=self.user,
            command="sudo systemctl poweroff",
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "no stderr"
            logger.error(
                "Worker shutdown command failed",
                extra={
                    "worker_host": self.host,
                    "returncode": result.returncode,
                    "stderr": stderr,
                },
            )
            raise WorkerManagerError(f"worker shutdown failed: {stderr}")

        self.mark_used()
        logger.info("Worker shutdown command sent", extra={"worker_host": self.host})

    def mark_used(self) -> None:
        self.last_used_at = datetime.now(timezone.utc)

    def seconds_since_last_used(self) -> int | None:
        if self.last_used_at is None:
            return None

        elapsed_seconds = (datetime.now(timezone.utc) - self.last_used_at).total_seconds()
        return max(0, int(elapsed_seconds))

    def is_idle(self) -> bool:
        seconds_since_last_used = self.seconds_since_last_used()
        if seconds_since_last_used is None:
            return False

        return seconds_since_last_used >= self.idle_timeout_seconds

    def shutdown_if_idle(self) -> dict[str, object]:
        if not self.is_online():
            logger.info("Skipping idle shutdown because worker is offline")
            return {"status": "offline"}

        seconds_since_last_used = self.seconds_since_last_used()
        if seconds_since_last_used is None:
            logger.info("Skipping idle shutdown because worker usage is not tracked yet")
            return {
                "status": "not_tracked",
                "idle": False,
                "remaining_seconds": None,
            }

        remaining_seconds = max(0, self.idle_timeout_seconds - seconds_since_last_used)
        if remaining_seconds > 0:
            logger.info(
                "Skipping idle shutdown because worker is not idle",
                extra={
                    "worker_host": self.host,
                    "remaining_seconds": remaining_seconds,
                },
            )
            return {
                "status": "active",
                "idle": False,
                "seconds_since_last_used": seconds_since_last_used,
                "remaining_seconds": remaining_seconds,
            }

        logger.info("Worker is idle, shutting down", extra={"worker_host": self.host})
        self.shutdown()
        return {
            "status": "shutdown_sent",
            "idle": True,
            "seconds_since_last_used": seconds_since_last_used,
            "remaining_seconds": 0,
        }
