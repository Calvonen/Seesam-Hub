import os
import shutil
import socket
import subprocess
from datetime import datetime
from typing import Any

from services.worker_manager import WorkerManager

UNKNOWN = "unknown"


class HealthManager:
    def __init__(self, worker_manager: WorkerManager) -> None:
        self.worker_manager = worker_manager

    def get_health(self) -> dict[str, Any]:
        return {
            "hub": self._hub_health(),
            "worker": self._worker_health(),
            "system": self._system_health(),
            "services": self._services_health(),
            "updates": self._updates_health(),
        }

    def _hub_health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "hostname": socket.gethostname(),
            "time": datetime.now().isoformat(timespec="seconds"),
            "uptime_seconds": self._uptime_seconds(),
        }

    def _worker_health(self) -> dict[str, object]:
        return {
            "host": self.worker_manager.host,
            "online": self._safe_worker_online(),
            "last_used_at": (
                self.worker_manager.last_used_at.isoformat()
                if self.worker_manager.last_used_at
                else None
            ),
            "idle_timeout_seconds": self.worker_manager.idle_timeout_seconds,
        }

    def _system_health(self) -> dict[str, object]:
        return {
            "disk_usage_percent": self._disk_usage_percent(),
            "memory_usage_percent": self._memory_usage_percent(),
            "load_average": self._load_average(),
        }

    def _services_health(self) -> dict[str, object]:
        return {
            "seesam_hub": self._systemd_service_status("seesam-hub"),
            "tailscale": self._tailscale_status(),
        }

    def _updates_health(self) -> dict[str, object]:
        return {
            "apt_updates_available_count": self._apt_updates_available_count(),
        }

    def _safe_worker_online(self) -> bool | str:
        try:
            return self.worker_manager.is_online()
        except Exception:
            return UNKNOWN

    def _uptime_seconds(self) -> int | str:
        try:
            with open("/proc/uptime", encoding="utf-8") as uptime_file:
                return int(float(uptime_file.read().split()[0]))
        except (OSError, IndexError, ValueError):
            return UNKNOWN

    def _disk_usage_percent(self) -> float | str:
        try:
            usage = shutil.disk_usage("/")
        except OSError:
            return UNKNOWN

        if usage.total == 0:
            return UNKNOWN

        return round((usage.used / usage.total) * 100, 1)

    def _memory_usage_percent(self) -> float | str:
        try:
            memory_info = self._read_meminfo()
        except OSError:
            return UNKNOWN

        total_kib = memory_info.get("MemTotal")
        available_kib = memory_info.get("MemAvailable")
        if not total_kib or available_kib is None:
            return UNKNOWN

        used_kib = total_kib - available_kib
        return round((used_kib / total_kib) * 100, 1)

    def _load_average(self) -> dict[str, float] | str:
        try:
            one_minute, five_minutes, fifteen_minutes = os.getloadavg()
        except OSError:
            return UNKNOWN

        return {
            "1m": round(one_minute, 2),
            "5m": round(five_minutes, 2),
            "15m": round(fifteen_minutes, 2),
        }

    def _systemd_service_status(self, service_name: str) -> str:
        result = self._run_read_only_command(["systemctl", "is-active", service_name])
        if result is None:
            return UNKNOWN

        status = result.stdout.strip()
        return status if status else UNKNOWN

    def _tailscale_status(self) -> str:
        result = self._run_read_only_command(["systemctl", "is-active", "tailscaled"])
        if result is not None and result.stdout.strip():
            return result.stdout.strip()

        result = self._run_read_only_command(["tailscale", "status"])
        if result is None:
            return UNKNOWN

        if result.returncode == 0:
            return "available"

        return UNKNOWN

    def _apt_updates_available_count(self) -> int | str:
        result = self._run_read_only_command(["apt", "list", "--upgradable"], timeout=8)
        if result is None or result.returncode != 0:
            return UNKNOWN

        update_lines = [
            line
            for line in result.stdout.splitlines()
            if line and not line.startswith("Listing...")
        ]
        return len(update_lines)

    def _read_meminfo(self) -> dict[str, int]:
        memory_info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as meminfo_file:
            for line in meminfo_file:
                key, value = line.split(":", maxsplit=1)
                memory_info[key] = int(value.strip().split()[0])
        return memory_info

    def _run_read_only_command(
        self,
        command: list[str],
        timeout: int = 3,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return None
