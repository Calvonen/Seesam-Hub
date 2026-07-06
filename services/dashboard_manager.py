from typing import Any, Callable

from services.health_manager import HealthManager
from services.update_manager import UpdateManager
from services.worker_manager import WorkerManager

UNKNOWN = "unknown"


class DashboardManager:
    def __init__(
        self,
        health_manager: HealthManager,
        update_manager: UpdateManager,
        worker_manager: WorkerManager,
    ) -> None:
        self.health_manager = health_manager
        self.update_manager = update_manager
        self.worker_manager = worker_manager

    def get_dashboard(self) -> dict[str, object]:
        return {
            "hub": self._safe_section(self._hub_section),
            "worker": self._safe_section(self._worker_section),
            "system": self._safe_section(self._system_section),
            "services": self._safe_section(self._services_section),
            "updates": self._safe_section(self._updates_section),
        }

    def _hub_section(self) -> dict[str, object]:
        return self.health_manager._hub_health()

    def _worker_section(self) -> dict[str, object]:
        return {
            "host": self.worker_manager.host,
            "online": self.worker_manager.is_online(),
            "last_used_at": (
                self.worker_manager.last_used_at.isoformat()
                if self.worker_manager.last_used_at
                else None
            ),
            "idle_timeout_seconds": self.worker_manager.idle_timeout_seconds,
            "idle": self.worker_manager.is_idle(),
            "seconds_since_last_used": self.worker_manager.seconds_since_last_used(),
        }

    def _system_section(self) -> dict[str, object]:
        return self.health_manager._system_health()

    def _services_section(self) -> dict[str, object]:
        return self.health_manager._services_health()

    def _updates_section(self) -> dict[str, object]:
        update_status = self.update_manager.get_update_status()
        apt_status = update_status.get("apt", {})
        firmware_status = update_status.get("firmware", {})

        if not isinstance(apt_status, dict):
            apt_status = {}
        if not isinstance(firmware_status, dict):
            firmware_status = {}

        return {
            "apt_updates_available_count": apt_status.get(
                "updates_available_count",
                UNKNOWN,
            ),
            "apt_packages": apt_status.get("packages", UNKNOWN),
            "firmware_updates_available": firmware_status.get(
                "updates_available",
                UNKNOWN,
            ),
            "firmware_updates_available_count": firmware_status.get(
                "updates_available_count",
                UNKNOWN,
            ),
            "firmware_summaries": firmware_status.get("summaries", UNKNOWN),
        }

    def _safe_section(self, section_loader: Callable[[], dict[str, Any]]) -> dict[str, Any] | str:
        try:
            return section_loader()
        except Exception:
            return UNKNOWN
