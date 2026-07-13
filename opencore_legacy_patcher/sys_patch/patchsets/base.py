"""
base.py: Hardened Base class for all patch sets
"""

from enum import Enum, auto
from pathlib import Path
from packaging import version
import subprocess
import os
import logging

# Set up logging for audit trails
logger = logging.getLogger(__name__)

class PatchType(Enum):
    """
    Type of patch using auto() to prevent string injection/manipulation
    """
    OVERWRITE_SYSTEM_VOLUME = auto()
    OVERWRITE_DATA_VOLUME = auto()
    MERGE_SYSTEM_VOLUME = auto()
    MERGE_DATA_VOLUME = auto()
    REMOVE_SYSTEM_VOLUME = auto()
    REMOVE_DATA_VOLUME = auto()
    EXECUTE = auto()

class DynamicPatchset(Enum):
    MetallibSupportPkg = auto()

class BasePatchset:
    # Whitelist of strictly allowed binaries for EXECUTE operations
    # Prevents arbitrary shell command injection
    _ALLOWED_EXECS = {
        "patcher_helper": "/usr/local/bin/patcher_helper",
    }

    def __init__(self) -> None:
        # Use semantic versioning objects, not floats, to prevent 
        # precision errors and enable accurate version comparisons.
        self.OS_VERSIONS = {
            "12.0_B7": version.parse("21.1.0"),
            "12.4":    version.parse("21.5.0"),
            "12.5":    version.parse("21.6.0"),
            "13.3":    version.parse("22.4.0"),
            "14.1":    version.parse("23.1.0"),
            "14.2":    version.parse("23.2.0"),
            "14.4":    version.parse("23.4.0"),
            "15.2":    version.parse("24.2.0"),
            "15.3":    version.parse("24.3.0"),
        }

    def is_compatible(self, current_version_str: str) -> bool:
        """Secure version comparison."""
        try:
            return version.parse(current_version_str) >= self.OS_VERSIONS["15.3"]
        except version.InvalidVersion:
            return False

    def validate_path(self, base_dir: str, target_path: str) -> Path:
        """Prevents Path Traversal attacks."""
        base = Path(base_dir).resolve()
        target = (base / target_path).resolve()
        
        if not target.startswith(base):
            raise PermissionError(f"Security Alert: Attempted path traversal: {target}")
        return target

    def secure_execute(self, binary_key: str, args: list[str]) -> subprocess.CompletedProcess:
        """
        Secure wrapper for execution. 
        Requires args to be a list to prevent shell injection.
        """
        if binary_key not in self._ALLOWED_EXECS:
            raise PermissionError(f"Unauthorized execution attempt: {binary_key}")
            
        cmd = [self._ALLOWED_EXECS[binary_key]] + args
        
        # Scrub environment variables to prevent LD_PRELOAD attacks
        safe_env = {k: v for k, v in os.environ.items() if k in ["PATH", "LANG"]}
        
        logger.info(f"Executing secure command: {' '.join(cmd)}")
        return subprocess.run(cmd, env=safe_env, check=True, capture_output=True)
