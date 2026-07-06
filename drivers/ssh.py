import subprocess


def run_ssh_command(host: str, user: str, command: str) -> subprocess.CompletedProcess[str]:
    """Run a command on a remote host over SSH."""
    return subprocess.run(
        ["ssh", f"{user}@{host}", command],
        check=False,
        capture_output=True,
        text=True,
    )
