import json
import subprocess
from typing import Any

UNKNOWN = "unknown"


class UpdateManager:
    def get_update_status(self) -> dict[str, object]:
        return {
            "apt": self._apt_status(),
            "firmware": self._firmware_status(),
        }

    def _apt_status(self) -> dict[str, object]:
        result = self._run_read_only_command(["apt", "list", "--upgradable"], timeout=8)
        if result is None or result.returncode != 0:
            return {
                "updates_available_count": UNKNOWN,
                "packages": UNKNOWN,
            }

        packages = self._parse_apt_package_names(result.stdout)
        return {
            "updates_available_count": len(packages),
            "packages": packages,
        }

    def _firmware_status(self) -> dict[str, object]:
        result = self._run_read_only_command(
            ["fwupdmgr", "get-updates", "--json"],
            timeout=10,
        )
        if result is None:
            return {
                "updates_available": UNKNOWN,
                "updates_available_count": UNKNOWN,
                "summaries": UNKNOWN,
            }

        if result.returncode != 0:
            if "no upgrades" in result.stdout.casefold():
                return {
                    "updates_available": False,
                    "updates_available_count": 0,
                    "summaries": [],
                }
            return {
                "updates_available": UNKNOWN,
                "updates_available_count": UNKNOWN,
                "summaries": UNKNOWN,
            }

        firmware_summaries = self._parse_fwupdmgr_summaries(result.stdout)
        if firmware_summaries == UNKNOWN:
            return {
                "updates_available": UNKNOWN,
                "updates_available_count": UNKNOWN,
                "summaries": UNKNOWN,
            }

        return {
            "updates_available": len(firmware_summaries) > 0,
            "updates_available_count": len(firmware_summaries),
            "summaries": firmware_summaries,
        }

    def _parse_apt_package_names(self, output: str) -> list[str]:
        packages: list[str] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or "/" not in line:
                continue

            package_name = line.split("/", maxsplit=1)[0].strip()
            if package_name:
                packages.append(package_name)

        return packages

    def _parse_fwupdmgr_summaries(self, output: str) -> list[str] | str:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            if "no upgrades" in output.casefold():
                return []
            return UNKNOWN

        devices = self._extract_fwupdmgr_devices(payload)
        summaries: list[str] = []
        for device in devices:
            summary = self._summarize_fwupdmgr_device(device)
            if summary:
                summaries.append(summary)

        return self._deduplicate(summaries)

    def _extract_fwupdmgr_devices(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            devices = value.get("Devices")
            if isinstance(devices, list):
                return [device for device in devices if isinstance(device, dict)]

            if isinstance(value.get("Name"), str) and (
                "Releases" in value or "Version" in value
            ):
                return [value]

            for nested_value in value.values():
                nested_devices = self._extract_fwupdmgr_devices(nested_value)
                if nested_devices:
                    return nested_devices

        if isinstance(value, list):
            devices: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("Name"), str):
                    devices.append(item)
                else:
                    devices.extend(self._extract_fwupdmgr_devices(item))
            return devices

        return []

    def _summarize_fwupdmgr_device(self, device: dict[str, Any]) -> str | None:
        name = device.get("Name") or device.get("name")
        if not isinstance(name, str):
            return None

        version = self._firmware_update_version(device)
        return f"{name} {version}" if version else name

    def _firmware_update_version(self, device: dict[str, Any]) -> str | None:
        releases = device.get("Releases") or device.get("releases")
        if isinstance(releases, list):
            for release in releases:
                if not isinstance(release, dict):
                    continue
                version = release.get("Version") or release.get("version")
                if isinstance(version, str):
                    return version

        version = device.get("Version") or device.get("version")
        return version if isinstance(version, str) else None

    def _deduplicate(self, values: list[str]) -> list[str]:
        deduplicated: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduplicated.append(value)
        return deduplicated

    def _run_read_only_command(
        self,
        command: list[str],
        timeout: int,
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
