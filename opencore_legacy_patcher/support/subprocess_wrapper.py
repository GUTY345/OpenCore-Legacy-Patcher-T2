"""
subprocess_wrapper.py: Wrapper for subprocess module to better handle errors and output
and to minimize repeated macOS GUI password prompts by caching an authenticated
sudo session per Python process when possible.
"""
import logging
import subprocess
import shlex
from typing import Union, List, Tuple

# State to track if this Python process has performed GUI authentication
_is_authenticated = False


def authenticate() -> None:
    """
    Trigger a single native macOS GUI password prompt to cache credentials
    for the current user session. This uses AppleScript to call "sudo -v"
    with administrator privileges which causes macOS to show the GUI dialog.
    """
    global _is_authenticated
    auth_script = 'do shell script "sudo -v" with administrator privileges'

    try:
        subprocess.run(["osascript", "-e", auth_script], check=True)
        _is_authenticated = True
        logging.info("Session authenticated successfully.")
    except subprocess.CalledProcessError:
        logging.error("Authentication failed or cancelled by user.")
        raise PermissionError("Root privileges are required to perform this action.")


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Basic subprocess.run wrapper.
    """
    return subprocess.run(*args, **kwargs)


def _is_authentication_failure(result: subprocess.CompletedProcess) -> bool:
    """
    Heuristic to detect sudo / authentication failure from a CompletedProcess.
    """
    try:
        stderr = result.stderr.decode("utf-8", errors="ignore") if isinstance(result.stderr, (bytes, bytearray)) else (str(result.stderr) if result.stderr is not None else "")
    except Exception:
        stderr = ""

    auth_markers = [
        "sudo: a password is required",
        "sudo: password for",
        "sudo: 3 incorrect password attempts",
        "Sorry, try again."
    ]

    if any(marker in stderr for marker in auth_markers):
        return True

    # Conservative fallback: sudo -n often returns 1 when the timestamp has expired
    if result.returncode == 1 and not stderr:
        return True

    return False


def _build_sudo_command(cmd: Union[str, List[str], Tuple[str, ...]], shell: bool) -> Union[List[str], str]:
    """
    Build the sudo command to pass to subprocess.run.

    - If cmd is a list/tuple, return a list like ["sudo", "-n", ...].
    - If cmd is a string and shell=True, return a string that runs via sh -c
      (the caller must execute with shell=True).
    - If cmd is a string and shell=False, split it safely with shlex.
    """
    if isinstance(cmd, (list, tuple)):
        return ["sudo", "-n"] + list(cmd)

    if shell:
        # run a quoted shell command under sudo non-interactively
        return f"sudo -n sh -c {shlex.quote(cmd)}"

    # split safely
    return ["sudo", "-n"] + shlex.split(cmd)


def run_as_root(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Run subprocess as root using a cached sudo session when possible.

    Usage examples:
      run_as_root(["/usr/sbin/installer", "-pkg", pkg_path, "-target", "/"])
      run_as_root("cmd1 && cmd2", shell=True)

    Behavior:
      - If this process has not called authenticate(), call it once (GUI prompt).
      - Attempt sudo -n which uses the cached timestamp without prompting.
      - If sudo -n appears to fail due to authentication, call authenticate() once
        and retry the command one time.

    Returns the subprocess.CompletedProcess for the final attempt.
    """
    global _is_authenticated

    if not args or not args[0]:
        raise ValueError("No command provided")

    # Copy kwargs so we can adjust shell without mutating caller's dict
    run_kwargs = dict(kwargs)
    shell = bool(run_kwargs.get("shell", False))
    cmd = args[0]

    # Ensure we have a cached sudo session in this process
    if not _is_authenticated:
        authenticate()

    sudo_cmd = _build_sudo_command(cmd, shell)

    # Decide how to call subprocess.run based on sudo_cmd type
    if isinstance(sudo_cmd, str):
        run_kwargs["shell"] = True
        attempt_args = (sudo_cmd,)
    else:
        run_kwargs["shell"] = False
        attempt_args = (sudo_cmd,)

    # Ensure we capture stderr to detect auth failures, but respect explicit
    # stdout/stderr settings from caller if provided
    run_kwargs.setdefault("capture_output", True)

    # First attempt: non-interactive sudo (uses cached timestamp)
    result = subprocess.run(*attempt_args, **run_kwargs)

    # If sudo failed because the timestamp expired, re-authenticate once and retry
    if _is_authentication_failure(result):
        logging.info("Cached sudo timestamp likely expired; prompting GUI once and retrying.")
        authenticate()
        result = subprocess.run(*attempt_args, **run_kwargs)

    return result


def verify(process_result: subprocess.CompletedProcess) -> None:
    """
    Verify process result and raise exception if failed.
    """
    if process_result.returncode == 0:
        return
    log(process_result)
    raise Exception(f"Process failed with exit code {process_result.returncode}")


def run_and_verify(*args, **kwargs) -> None:
    """
    Run subprocess and verify result.
    """
    verify(run(*args, **kwargs))


def run_as_root_and_verify(*args, **kwargs) -> None:
    """
    Run subprocess as root and verify result.
    """
    verify(run_as_root(*args, **kwargs))


def log(process: subprocess.CompletedProcess) -> None:
    """
    Display subprocess error output in formatted string.
    """
    for line in generate_log(process).split("\n"):
        logging.error(line)


def generate_log(process: subprocess.CompletedProcess) -> str:
    """
    Generate a formatted log of subprocess failure.
    """
    output = "Subprocess failed.\n"
    output += f" Command: {process.args}\n"
    output += f" Return Code: {process.returncode}\n"
    output += "    Standard Output:\n"
    if process.stdout:
        stdout_bytes = process.stdout
        output += __format_output(stdout_bytes.decode("utf-8") if isinstance(stdout_bytes, (bytes, bytearray)) else str(stdout_bytes))
    else:
        output += "        None\n"

    output += "    Standard Error:\n"
    if process.stderr:
        stderr_bytes = process.stderr
        output += __format_output(stderr_bytes.decode("utf-8") if isinstance(stderr_bytes, (bytes, bytearray)) else str(stderr_bytes))
    else:
        output += "        None\n"

    return output


def __format_output(output: str) -> str:
    """
    Helper to indent log lines for readability.
    """
    if not output:
        return " None\n"
    _result = "\n".join([f"        {line}" for line in output.split("\n") if line.strip()])
    if not _result.endswith("\n"):
        _result += "\n"
    return _result
