"""
updates.py: Check for OpenCore Legacy Patcher binary updates
"""
import logging
import sys
from typing import Optional, Union
from packaging import version
from . import network_handler
from .. import constants

REPO_LATEST_RELEASE_URL: str = "https://api.github.com/repos/albert-mueller/OpenCore-Legacy-Patcher-T2/releases/latest"

class CheckBinaryUpdates:
    def __init__(self, global_constants: constants.Constants) -> None:
        self.constants: constants.Constants = global_constants
        try:
            self.binary_version = version.parse(self.constants.patcher_version)
        except (version.InvalidVersion, TypeError):
            assert self.constants.special_build is True, "Invalid version number for binary"
            self.binary_version = version.parse("0.0.0")
        self.latest_details = None

    def check_if_newer(self, version_to_check: Union[str, version.Version]) -> bool:
        if self.constants.special_build is True:
            return False
        return self._check_if_build_newer(version_to_check, self.binary_version)

    def _check_if_build_newer(self, first_version: Union[str, version.Version], second_version: Union[str, version.Version]) -> bool:
        if not isinstance(first_version, version.Version):
            try:
                first_version = version.parse(first_version)
            except version.InvalidVersion:
                return True # Special/Nightly build logic
        
        if not isinstance(second_version, version.Version):
            try:
                second_version = version.parse(second_version)
            except version.InvalidVersion:
                return False

        if first_version == second_version:
            # Falls Versionen identisch, prüfen ob es ein Nightly-Build ist [4, 5]
            if not self.constants.commit_info.startswith("refs/tags"):
                return True
        return first_version > second_version

    def check_binary_updates(self) -> Optional[dict]:
        """ Überprüft auf Updates und gibt Details inkl. Changelog zurück """
        if self.constants.special_build is True:
            return None
        
        if self.latest_details:
            return self.latest_details

        if not network_handler.NetworkUtilities(REPO_LATEST_RELEASE_URL).verify_network_connection():
            return None

        try:
            # FIX: Sicherer Abruf und Fehlerbehandlung beim Parsen [1]
            response = network_handler.NetworkUtilities().get(REPO_LATEST_RELEASE_URL)
            if not response:
                return None
            data_set = response.json()
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der GitHub-Daten: {e}")
            return None

        if "tag_name" not in data_set:
            logging.warning("GitHub-Antwort unvollständig (evtl. Rate-Limit erreicht).")
            return None

        try:
            latest_remote_version = version.parse(data_set["tag_name"])
        except version.InvalidVersion:
            return None

        if not self._check_if_build_newer(latest_remote_version, self.binary_version):
            return None

        for asset in data_set.get("assets", []):
            logging.info(f"Prüfe Asset: {asset['name']}")
            # FIX: Flexiblere Suche nach dem Installer-Paket
            if asset["name"].endswith(".pkg") and "OpenCore-Patcher" in asset["name"]:
                self.latest_details = {
                    "Name": asset["name"],
                    "Version": str(latest_remote_version),
                    "Link": asset["browser_download_url"],
                    # FIX: Nutzen des echten GitHub-Links und mitschicken des Changelogs
                    "Github Link": data_set.get("html_url", f"https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2/releases/tag/{latest_remote_version}"),
                    "Changelog": data_set.get("body", "") 
                }
                return self.latest_details
        
        return None
