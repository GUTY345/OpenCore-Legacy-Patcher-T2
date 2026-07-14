"""
subprocess_wrapper.py: Wrapper for subprocess module to handle 
privileged operations with a session-based cache to prevent 
repeated password prompts.
"""
import logging
import subprocess
import shlex
import sys

# Persistent state to track authentication
_is_authenticated = False

def authenticate():
    """
    Triggers the native macOS GUI password prompt exactly once.
    This primes the sudo cache for subsequent 'sudo -n' calls.
    """
    global _is_authenticated
    # 'do shell script' via osascript is the only way to trigger the native
    # macOS GUI password dialog from a Python application.
    auth_script = 'do shell script "sudo -v" with administrator privileges'
    
    try:
        logging.info("Priming authentication cache...")
        subprocess.run(["osascript", "-e", auth_script], check=True)
        _is_authenticated = True
        logging.info("Authentication primed successfully.")
    except subprocess.CalledProcessError:
        logging.error("Authentication failed or cancelled by user.")
        raise PermissionError("Root privileges are required for this operation.")

def run(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Standard run wrapper for unprivileged commands.
    """
    return subprocess.run(*args, **kwargs)

def run_as_root(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Executes commands as root using a non-interactive sudo session.
    Automatically authenticates if no session exists.
    """
    if not _is_authenticated:
        authenticate()
    
    # We use 'sudo -n' (non-interactive) to rely on the primed cache.
    # This ensures commands execute instantly without re-prompting.
    full_cmd = ["sudo", "-n"] + list(args[0])
    
    return subprocess.run(full_cmd, **kwargs)

def verify(process_result: subprocess.CompletedProcess) -> None:
    """
    Checks if a subprocess finished with a success code.
    """
    if process_result.returncode == 0:
        return
    log(process_result)
    raise Exception(f"Process failed with exit code {process_result.returncode}")

def run_as_root_and_verify(*args, **kwargs) -> None:
    """
    Convenience method to run as root and fail loudly if needed.
    """
    verify(run_as_root(*args, **kwargs))

def log(process: subprocess.CompletedProcess) -> None:
    """
    Helper to format and log failed subprocess output.
    """
    for line in generate_log(process).split("\n"):
        logging.error(line)

def generate_log(process: subprocess.CompletedProcess) -> str:
    """
    Formats the stderr/stdout for easier debugging.
    """
    output = f"Subprocess failed.\n Command: {process.args}\n Return Code: {process.returncode}\n"
    output += "    Standard Output:\n"
    output += __format_output(process.stdout.decode("utf-8") if process.stdout else "None")
    output += "    Standard Error:\n"
    output += __format_output(process.stderr.decode("utf-8") if process.stderr else "None")
    return output

def __format_output(output: str) -> str:
    if not output:
        return "        None\n"
    return "\n".join([f"        {line}" for line in output.split("\n") if line.strip()]) + "\n"
