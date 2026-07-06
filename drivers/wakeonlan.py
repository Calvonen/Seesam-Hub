import logging
import subprocess

logger = logging.getLogger(__name__)


def send_magic_packet(mac_address: str) -> None:
    """Send a Wake-on-LAN magic packet with the system wakeonlan command."""
    logger.info("Sending Wake-on-LAN magic packet", extra={"worker_mac": mac_address})

    try:
        subprocess.run(
            ["wakeonlan", mac_address],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        logger.exception("wakeonlan command was not found")
        raise RuntimeError("wakeonlan command was not found") from exc
    except subprocess.CalledProcessError as exc:
        logger.exception("wakeonlan command failed")
        stderr = exc.stderr.strip() if exc.stderr else "no stderr"
        raise RuntimeError(f"wakeonlan command failed: {stderr}") from exc
