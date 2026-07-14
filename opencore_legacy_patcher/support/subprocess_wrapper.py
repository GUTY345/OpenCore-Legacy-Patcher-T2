"""
subprocess_wrapper.py: Wrapper for subprocess module to better handle errors and output
using session-based authentication to eliminate prompt fatigue.
"""
import logging
import subprocess
import shlex

# State to track if the session is currently authenticated
_is_authenticated = False

def authenticate():
    """
    Triggers one single native macOS GUI password prompt to cache credentials.
    """
    global _is_authenticated
    # 'do shell script "sudo -v" with administrator privileges' is the 
    # specific bridge that forces macOS to show the GUI password dialog.
    # Once entered, the system caches the credentials for the current session.
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
    Basic subprocess.run wrapper for unprivileged commands.
    """
    return subprocess.run(*args, **kwargs)

def run_as_root(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Run subprocess as root using cached sudo session.
    Automatically authenticates if no session exists.
    """
    if not _is_authenticated:
        authenticate()
    
    if not args or not args[0]:
        raise ValueError("No command provided")
    
    # Use -n (non-interactive). It will use the cached token from 
    # authenticate() and fail if the session has expired.
    # This prevents the script from hanging on unexpected prompts.
    gui_command = ["sudo", "-n"] + list(args[0])
    
    return subprocess.run(gui_command, **kwargs)

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
        output += __format_output(process.stdout.decode("utf-8"))
    else:
        output += "        None\n"

    output += "    Standard Error:\n"
    if process.stderr:
        output += __format_output(process.stderr.decode("utf-8"))
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
