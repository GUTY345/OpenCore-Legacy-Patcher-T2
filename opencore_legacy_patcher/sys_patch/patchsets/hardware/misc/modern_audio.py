"""
modern_audio.py: Modern Audio patch set for macOS 26
"""

import os
from ..base import BaseHardware, HardwareVariant
from ...base import PatchType
from .....constants import Constants
from .....datasets.os_data import os_data

class ModernAudio(BaseHardware):
    # Registry now uses a range-based strategy
    _MINIMUM_MODERN_AUDIO_OS = 26  # Version 26.0

    def __init__(self, xnu_major, xnu_minor, os_build, global_constants: Constants) -> None:
        super().__init__(xnu_major, xnu_minor, os_build, global_constants)

    def name(self) -> str:
        return f"{self.hardware_variant()}: Modern Audio"

    def present(self) -> bool:
        return True

    def native_os(self) -> bool:
        """
        Uses version comparison rather than string matching.
        Native if:
        1. XNU major version is strictly less than 26.
        2. Or, if it is 26, we check against a build-specific whitelist.
        """
        # Everything clearly older than 26 is native
        if self._xnu_major < self._MINIMUM_MODERN_AUDIO_OS:
            return True

        # If we are on 26+, we only consider it native if the build is in the 
        # explicitly supported native list. 
        # This handles the 'Beta 1' edge case without breaking future versions.
        native_builds = {"25A5279M"}
        
        # We only return False (non-native) if we are on 26+ and the build isn't whitelisted.
        if self._xnu_major >= self._MINIMUM_MODERN_AUDIO_OS:
            if str(self._os_build).upper() in native_builds:
                return True
            return False

        return False

    def hardware_variant(self) -> HardwareVariant:
        return HardwareVariant.MISCELLANEOUS

    def _modern_audio_patches(self) -> dict:
        """
        Uses a static path registry to prevent ACE/Injection vulnerabilities.
        """
        return {
            "Modern Audio": {
                PatchType.OVERWRITE_SYSTEM_VOLUME: {
                    "/System/Library/Extensions": {
                        "AppleHDA.kext": "26.0+", # Generic target for 26+
                    },
                },
            },
        }

    def patches(self) -> dict:
        """
        Safe patch entry point.
        """
        # If native, return no patches
        if self.native_os():
            return {}

        # If we are here, we are on 26.0+ and it is NOT native.
        # This automatically applies to all 26.x versions past Beta 1.
        return self._modern_audio_patches()
