"""
utilities.py: Utility functions for OpenCore Legacy Patcher
"""

import os
import re
import math
import atexit
import shutil
import logging
import argparse
import binascii
import plistlib
import subprocess
import py_sip_xnu

from pathlib import Path

from .. import constants

from ..detections import ioreg

from ..datasets import (
    os_data,
    sip_data
)


def hexswap(input_hex: str):
    hex_pairs = [input_hex[i : i + 2] for i in range(0, len(input_hex), 2)]
    hex_rev = hex_pairs[::-1]
    hex_str = "".join(["".join(x) for x in hex_rev])
    return hex_str.upper()


def string_to_hex(input_string):
    if not (len(input_string) % 2) == 0:
        input_string = "0" + input_string
    input_string = hexswap(input_string)
    input_string = binascii.unhexlify(input_string)
    return input_string


def human_fmt(num):
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num) < 1000.0:
            return "%3.1f %s" % (num, unit)
        num /= 1000.0
    return "%.1f %s" % (num, "EB")


def seconds_to_readable_time(seconds) -> str:
    """
    Convert seconds to a readable time format

    Parameters:
        seconds (int | float | str): Seconds to convert

    Returns:
        str: Readable time format
    """
    seconds = int(seconds)
    time = ""

    if 0 <= seconds < 60:
        return "Less than a minute "
    if seconds < 0:
        return "Indeterminate time "

    years, seconds = divmod(seconds, 31536000)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if years > 0:
        return "Over a year"
    if days > 0:
        if days > 31:
            return "Over a month"
        time += f"{days}d "
    if hours > 0:
        time += f"{hours}h "
    if minutes > 0:
        time += f"{minutes}m "
    #if seconds > 0:
    #    time += f"{seconds}s"
    return time


def header(lines):
    lines = [i for i in lines if i is not None]
    total_length = len(max(lines, key=len)) + 4
    logging.info("#" * (total_length))
    for line in lines:
        left_side = math.floor(((total_length - 2 - len(line.strip())) / 2))
        logging.info("#" + " " * left_side + line.strip() + " " * (total_length - len("#" + " " * left_side + line.strip()) - 1) + "#")
    logging.info("#" * total_length)


RECOVERY_STATUS = None


def check_recovery():
    global RECOVERY_STATUS  # pylint: disable=global-statement # We need to cache the result

    if RECOVERY_STATUS is None:
        RECOVERY_STATUS = Path("/System/Library/BaseSystem").exists()

    return RECOVERY_STATUS


def get_disk_path():
    root_partition_info = plistlib.loads(subprocess.run(["/usr/sbin/diskutil", "info", "-plist", "/"], stdout=subprocess.PIPE).stdout.decode().strip().encode())
    root_mount_path = root_partition_info["DeviceIdentifier"]
    root_mount_path = root_mount_path[:-2] if root_mount_path.count("s") > 1 else root_mount_path
    return root_mount_path


def check_if_root_is_apfs_snapshot():
    root_partition_info = plistlib.loads(subprocess.run(["/usr/sbin/diskutil", "info", "-plist", "/"], stdout=subprocess.PIPE).stdout.decode().strip().encode())
    try:
        is_snapshotted = root_partition_info["APFSSnapshot"]
    except KeyError:
        is_snapshotted = False
    return is_snapshotted


def check_seal():
    # 'Snapshot Sealed' property is only listed on booted snapshots
    sealed = subprocess.run(["/usr/sbin/diskutil", "apfs", "list"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if "Snapshot Sealed:           Yes" in sealed.stdout.decode():
        return True
    else:
        return False

def check_filesystem_type():
    # Expected to return 'apfs' or 'hfs'
    filesystem_type = plistlib.loads(subprocess.run(["/usr/sbin/diskutil", "info", "-plist", "/"], stdout=subprocess.PIPE).stdout.decode().strip().encode())
    return filesystem_type["FilesystemType"]


def find_any_oclp_manifest(root_path: Path = None):
    """
    Search common locations for any OpenCore Legacy Patcher root-volume
    manifest left behind by a previous root patch, regardless of which
    OCLP version originally wrote it.

    Returns the Path to the first manifest found, or None if none exists.
    """
    if root_path is None:
        root_path = Path("/")

    search_dirs = [
        root_path / "System" / "Library" / "CoreServices",
        root_path / "Library" / "Application Support" / "Dortania",
    ]

    for directory in search_dirs:
        try:
            if not directory.is_dir():
                continue
            for candidate in directory.iterdir():
                # Note: 'pathlib.Path.glob()' matches case-sensitively even on
                # case-insensitive filesystems (default macOS APFS included),
                # since the pattern matching itself happens in Python, not the OS.
                # The real file OCLP writes is mixed-case
                # ("OpenCore-Legacy-Patcher.plist"), which a lowercase glob
                # pattern will never match, so match case-insensitively instead.
                if candidate.is_file() and "opencore-legacy-patcher" in candidate.name.lower():
                    return candidate
        except (OSError, PermissionError):
            continue

    return None


def csr_decode(os_sip):
    sip_int = py_sip_xnu.SipXnu().get_sip_status().value
    for i,  current_sip_bit in enumerate(sip_data.system_integrity_protection.csr_values):
        if sip_int & (1 << i):
            sip_data.system_integrity_protection.csr_values[current_sip_bit] = True

    # Can be adjusted to whatever OS needs patching
    sip_needs_change = all(sip_data.system_integrity_protection.csr_values[i] for i in os_sip)
    if sip_needs_change is True:
        return False
    else:
        return True


def friendly_hex(integer: int):
    return "{:02X}".format(integer)

sleep_process = None

def disable_sleep_while_running():
    global sleep_process
    logging.info("Disabling Idle Sleep")
    if sleep_process is None:
        # If sleep_process is active, we'll just keep it running
        sleep_process = subprocess.Popen(["/usr/bin/caffeinate", "-d", "-i", "-s"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Ensures that if we don't properly close the process, 'atexit' will for us
    atexit.register(enable_sleep_after_running)

def enable_sleep_after_running():
    global sleep_process
    if sleep_process:
        logging.info("Re-enabling Idle Sleep")
        sleep_process.kill()
        sleep_process = None
