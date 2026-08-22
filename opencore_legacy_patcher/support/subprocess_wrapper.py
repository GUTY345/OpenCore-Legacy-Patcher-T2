"""
subprocess_wrapper.py: Wrapper for subprocess module to better handle errors and output
                       Additionally handles our Privileged Helper Tool
"""

import enum
import logging
import os
import shlex
import stat
import subprocess

import applescript

from pathlib import Path


OCLP_PRIVILEGED_HELPER = "/Library/PrivilegedHelperTools/com.dortania.opencore-legacy-patcher.privileged-helper"


class PrivilegedHelperErrorCodes(enum.IntEnum):
    """
    Error codes for Privileged Helper Tool.

    Reference:
        payloads/Tools/PrivilegedHelperTool/main.m
    """
    OCLP_PHT_ERROR_MISSING_ARGUMENTS           = 160
    OCLP_PHT_ERROR_SET_UID_MISSING             = 161
    OCLP_PHT_ERROR_SET_UID_FAILED              = 162
    OCLP_PHT_ERROR_SELF_PATH_MISSING           = 163
    OCLP_PHT_ERROR_PARENT_PATH_MISSING         = 164
    OCLP_PHT_ERROR_SIGNING_INFORMATION_MISSING = 165
    OCLP_PHT_ERROR_INVALID_TEAM_ID             = 166
    OCLP_PHT_ERROR_INVALID_CERTIFICATES        = 167
    OCLP_PHT_ERROR_COMMAND_MISSING             = 168
    OCLP_PHT_ERROR_COMMAND_FAILED              = 169
    OCLP_PHT_ERROR_CATCH_ALL                   = 170


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Basic subprocess.run wrapper.
    """
    return subprocess.run(*args, **kwargs)


def run_as_root(*args, **kwargs) -> subprocess.CompletedProcess:
    """
    Run subprocess as root.

    Note: Full path to first argument is required.
    Helper tool does not resolve PATH.
    """
    # Check if first argument exists
    if not Path(args[0][0]).exists():
        raise FileNotFoundError(f"File not found: {args[0][0]}")

    return subprocess.run([OCLP_PRIVILEGED_HELPER] + [args[0][0]] + args[0][1:], **kwargs)


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

    Asserts on failure.
    """
    verify(run(*args, **kwargs))


def run_as_root_and_verify(*args, **kwargs) -> None:
    """
    Run subprocess as root and verify result.

    Asserts on failure.
    """
    verify(run_as_root(*args, **kwargs))


def privileged_helper_needs_repair() -> bool:
    """
    Check whether the Privileged Helper Tool is actually usable.

    Context: the helper binary is meant to be installed SUID-root (see
    ci_tooling/privileged_helper_tool/install.sh and the .pkg postinstall
    script), but both only ever run "chmod +s" on it. "chmod +s" sets the
    SUID bit without touching the execute bits - if the file it's copying
    ever lacked an execute bit to begin with (e.g. a git-tracked binary
    committed with file mode 644 instead of 755), the result is a file
    with the SUID bit set but no execute bit for the kernel to honor it
    with, so any invocation from a normal user fails immediately with
    PermissionError: [Errno 13] Permission denied - before the helper's
    own code (Team ID/signature checks, etc.) ever runs.

    Returns True only if the helper exists but is missing something it
    needs (execute permission for the current user, or the SUID bit).
    Returns False if it's missing entirely - that's a "the helper was
    never installed" situation, not a permissions one, and chmod can't
    fix a file that isn't there.
    """
    if not Path(OCLP_PRIVILEGED_HELPER).exists():
        return False

    if not os.access(OCLP_PRIVILEGED_HELPER, os.X_OK):
        return True

    mode = stat.S_IMODE(os.stat(OCLP_PRIVILEGED_HELPER).st_mode)
    if not (mode & stat.S_ISUID):
        return True

    return False


def repair_privileged_helper_permissions() -> bool:
    """
    Repair the Privileged Helper Tool's permissions (chmod 4755) via a
    one-off admin-authenticated shell command.

    Deliberately does NOT go through run_as_root() (i.e. the helper tool
    itself) to do this - that's the same broken binary this function
    exists to fix, so routing through it here would just reproduce the
    original PermissionError instead of resolving it.

    Also deliberately NOT routed through "do shell script ... with
    administrator privileges" - see dmg_mount.py's _request_admin_password()
    for why that mechanism has caused issues elsewhere in this codebase.
    Instead, same as there: a plain AppleScript dialog collects the admin
    password and we feed it to sudo ourselves.
    """
    if not Path(OCLP_PRIVILEGED_HELPER).exists():
        return False

    try:
        password = applescript.AppleScript(
            'set theResult to display dialog '
            '"OpenCore Legacy Patcher T2 needs administrator access to repair its Privileged Helper Tool\'s permissions." '
            'default answer "" with hidden answer with title "OpenCore Legacy Patcher T2"'
            '\nreturn the text returned of theResult'
        ).run()
    except Exception:
        password = ""

    if not password:
        logging.info("Privileged Helper Tool permission repair cancelled (no administrator password provided)")
        return False

    cmd = ["/usr/bin/sudo", "-S", "/bin/chmod", "4755", shlex.quote(OCLP_PRIVILEGED_HELPER)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = process.communicate(input=(password + "\n").encode())

    if process.returncode != 0:
        logging.error(f"Failed to repair Privileged Helper Tool permissions: {stdout.decode(errors='replace').strip()}")
        return False

    logging.info("Repaired Privileged Helper Tool permissions")
    return True


def ensure_privileged_helper_permissions() -> None:
    """
    Self-healing check for the Privileged Helper Tool's permissions.

    No-op, with no prompt of any kind, when the helper is already fine or
    isn't installed yet - only reaches for an admin prompt when a repair
    is actually needed. Safe to call unconditionally (e.g. once per app
    launch, ahead of checking for updates): it doesn't touch the network
    or depend on it either way.
    """
    if not privileged_helper_needs_repair():
        return

    logging.info("Privileged Helper Tool is missing its execute or SUID bit, requesting administrator access to repair it")
    repair_privileged_helper_permissions()


def log(process: subprocess.CompletedProcess) -> None:
    """
    Display subprocess error output in formatted string.
    """
    for line in generate_log(process).split("\n"):
        logging.error(line)


def generate_log(process: subprocess.CompletedProcess) -> str:
    """
    Display subprocess error output in formatted string.
    Note this function is still used for zero return code errors, since
    some software don't ever return non-zero regardless of success.

    Format:

        Command: <command>
        Return Code: <return code>
        Standard Output:
            <standard output line 1>
            <standard output line 2>
            ...
        Standard Error:
            <standard error line 1>
            <standard error line 2>
            ...
    """
    output = "Subprocess failed.\n"
    output += f"    Command: {process.args}\n"
    output += f"    Return Code: {process.returncode}\n"
    _returned_error = __resolve_privileged_helper_errors(process.returncode)
    if _returned_error:
        output += f"        Likely Enum: {_returned_error}\n"
    output += f"    Standard Output:\n"
    if process.stdout:
        output += __format_output(process.stdout.decode("utf-8"))
    else:
        output += "        None\n"
    output += f"    Standard Error:\n"
    if process.stderr:
        output += __format_output(process.stderr.decode("utf-8"))
    else:
        output += "        None\n"

    return output


def __resolve_privileged_helper_errors(return_code: int) -> str:
    """
    Attempt to resolve Privileged Helper Tool error codes.
    """
    if return_code not in [error_code.value for error_code in PrivilegedHelperErrorCodes]:
        return None

    return PrivilegedHelperErrorCodes(return_code).name


def __format_output(output: str) -> str:
    """
    Format output.
    """
    if not output:
        # Shouldn't happen, but just in case
        return "        None\n"

    _result = "\n".join([f"        {line}" for line in output.split("\n") if line not in ["", "\n"]])
    if not _result.endswith("\n"):
        _result += "\n"

    return _result
