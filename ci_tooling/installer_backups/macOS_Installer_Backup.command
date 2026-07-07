#!/usr/bin/env python3

"""
--------------------------------
macOS_Installer_Backup.command
--------------------------------

Utility for grabbing macOS Installers from Apple's catalogs and AppleDB,
and saving them to a local directory.

WARNING: Solely for internal usage, not intended for end-users.
"""

import sys
import argparse
import plistlib
# subprocess wird nicht mehr für mv/rm benötigt, aber noch für dl_obj.download(spawn_thread=True)
import subprocess

from pathlib import Path
from datetime import datetime

# To allow easy importing of OpenCore Legacy Patcher's utilities
sys.path.append(str(Path(__file__).parent.parent.parent))

from opencore_legacy_patcher.support import (
    macos_installer_handler,
    network_handler,
    integrity_verification,
    utilities,
)
from opencore_legacy_patcher.datasets import os_data


_DEFAULT_PATH: str = "/Volumes/macOS Installers"


class InstallerBackup:

    def __init__(self,
                 directory:      Path = Path(_DEFAULT_PATH),
                 supported_oses: list = [
                     os_data.os_data.big_sur,
                     os_data.os_data.monterey,
                     os_data.os_data.ventura,
                     os_data.os_data.sonoma,
                     os_data.os_data.sequoia,
                     os_data.os_data.tahoe,
                    ],
                 first_run:      bool = False
                 ) -> None:

        print(f"Starting macOS Installer Backup: {datetime.now()}")

        self._directory = directory
        self._supported_oses = supported_oses

        self._os_table = {
            os_data.os_data.big_sur:  Path(self._directory, "11 Big Sur"),
            os_data.os_data.monterey: Path(self._directory, "12 Monterey"),
            os_data.os_data.ventura:  Path(self._directory, "13 Ventura"),
            os_data.os_data.sonoma:   Path(self._directory, "14 Sonoma"),
            os_data.os_data.sequoia:  Path(self._directory, "15 Sequoia"),
            os_data.os_data.tahoe:    Path(self._directory, "26 Tahoe"),
        }

        for os_version in self._supported_oses:
            if os_version not in self._os_table:
                raise ValueError(f"Unsupported OS version: {os_version}")

        for dir in self._os_table.values():
            if not Path(dir).exists():
                if first_run is False:
                    raise FileNotFoundError(f"Directory does not exist: {dir} (use --first-run to create)")
                Path(dir).mkdir(parents=True, exist_ok=True)

        self._main()


    def _download_installer(self, installer: dict) -> None:
        """
        Download installer
        """

        installer_name = f"{installer['Version']} ({installer['Build']})"
        if Path(installer['Link']).suffix == ".pkg":
            installer_name += " InstallAssistant.pkg"
        else:
            installer_name += " Restore.ipsw"
        integrity_name = f"{installer_name}.integrityDataV1"
        print(f"Downloading {installer_name}")

        # Check if integrity file available
        integrity = installer["integrity"]
        if integrity is not None:
            result = self._downloader(url=integrity, path=Path(self._os_table[installer['OS']], integrity_name), name=integrity_name)
            if result is False:
                return

        # Download installer
        result = self._downloader(url=installer["Link"], path=Path(self._os_table[installer['OS']], installer_name), name=installer_name)
        if result is False:
            return

        # Validate against chunklist
        if integrity is not None:
            result = self._validate_against_chunklist(installer_path=Path(self._os_table[installer['OS']], installer_name), chunklist=Path(self._os_table[installer['OS']], integrity_name))
            if result is False:
                return


    def _validate_against_chunklist(self, installer_path: Path, chunklist: Path) -> bool:
        """
        Validate file against chunklist (Using pathlib for safety)
        """

        name = Path(installer_path).name

        if not installer_path.exists():
            print("File does not exist")
            return False

        if not chunklist.exists():
            print("Chunklist does not exist")
            return False

        chunk_obj = integrity_verification.ChunklistVerification(str(installer_path), str(chunklist))
        if not chunk_obj.chunks:
            print("Failed to generate chunklist dict")
            return False

        print(f"Validating {name} against chunklist: {chunk_obj.total_chunks} chunks", end="\r")
        chunk_obj.validate()

        while chunk_obj.status == integrity_verification.ChunklistStatus.IN_PROGRESS:
            print(f"Validating {name} against chunklist: chunk {chunk_obj.current_chunk} passed", end="\r")

        if chunk_obj.status == integrity_verification.ChunklistStatus.FAILURE:
            print(chunk_obj.error_msg)
            print(f"Validating {name} against chunklist: chunk {chunk_obj.current_chunk} failed")
            # -- SICHERHEITS-FIX: Native pathlib Methoden verwenden ---
            for file_path in [installer_path, chunklist]:
                try:
                    file_path.unlink(missing_ok=True) # Ersetzt rm -f
                    print(f"Deleted {file_path}")
                except OSError as e:
                    print(f"Failed to delete {file_path}: {e}")
            # ---------------------------------------------------------

        print(f"Validating {name} against chunklist: chunk {chunk_obj.total_chunks} passed")
        return True


    def _downloader(self, url, path, name) -> bool:
        """
        Download file from URL
        """
        dl_obj = network_handler.DownloadObject(url, path)
        dl_obj.download(display_progress=False, spawn_thread=True)

        percentages_displayed = set()
        while dl_obj.is_active():
            if dl_obj.get_percent() in percentages_displayed:
                continue
            percentages_displayed.add(int(dl_obj.get_percent()))
            print(f"  Downloading: {name}: {dl_obj.get_percent():.2f}%  ({utilities.human_fmt(dl_obj.get_speed())})/s", end="\r")

        print(f"  Downloading: {name}: 100.00%  ({utilities.human_fmt(dl_obj.get_speed())})/s")

        if not dl_obj.download_complete:
            print("Download failed")
            # -- SICHERHEITS-FIX: Native pathlib Methode verwenden ---
            try:
                Path(path).unlink(missing_ok=True) # Ersetzt rm -f
                print(f"Deleted incomplete file: {path}")
            except OSError as e:
                print(f"Failed to delete incomplete file {path}: {e}")
            # ---------------------------------------------------------
            return False


        if Path(path).stat().st_size == 0:
            print("Downloaded file is empty, considering permanent failure") # Likely dead URL
            dead_urls_dir = Path(Path(path).parent, "Dead URLs")
            if not dead_urls_dir.exists():
                dead_urls_dir.mkdir()

            if Path(path).exists():
                dest_path = Path(dead_urls_dir, Path(path).name)
                # -- SICHERHEITS-FIX: Native pathlib Methode verwenden ---
                try:
                    Path(path).replace(dest_path) # Ersetzt mv
                    print(f"Moved empty file to {dest_path}")
                except OSError as e:
                    print(f"Failed to move empty file {path} to {dest_path}: {e}")
                # ---------------------------------------------------------

        return True



    def _does_file_exist(self, xnu_version: int, build: str, suffix: str) -> bool:
        """
        Check if installer already exists in directory
        """
        if xnu_version not in self._os_table:
            raise ValueError(f"Unsupported OS version: {xnu_version}")

        target_dir = Path(self._os_table[xnu_version])
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory does not exist: {target_dir}")

        # Check failed, as those are generally dead URLs
        for path in [target_dir, Path(target_dir, "Dead URLs")]:
            if not path.exists():
                continue
            for file in path.iterdir():
                if file.is_dir():
                    continue
                if not file.name.endswith(suffix):
                    continue
                if f"({build})" in file.name:
                    return True

        return False


    def _get_remote_installer_catalog(self, os_version: int) -> dict:
        """
        Get remote installer catalog from Apple's servers
        """
        installers = {}
        print(f"SUCATALOG: Getting installers for macOS {os_data.os_conversion.kernel_to_os(os_version)}")
        for seed in macos_installer_handler.SeedType:
            print(f"  Catalog: {seed.name}")
            result = macos_installer_handler.RemoteInstallerCatalog(seed_override=seed, os_override=os_version).available_apps
            installers.update(result)

        return installers


    def _get_apple_db_items(self, variant: str = ".ipsw") -> dict:
        """
        Get macOS installers from AppleDB
        """

        if variant not in ["InstallAssistant.pkg", ".ipsw"]:
            raise ValueError(f"Invalid variant: {variant}")

        installers = {}
        print(f"APPLEDB: Getting installers for variant: {variant}")

        apple_db_resp = network_handler.NetworkUtilities().get("https://api.appledb.dev/main.json")
        if apple_db_resp is None:
            return installers

        apple_db = apple_db_resp.json()
        for group in apple_db:
            if group != "ios":
                continue
            for item in apple_db[group]:
                if "osStr" not in item:
                    continue
                if item["osStr"] != "macOS":
                    continue
                if "build" not in item:
                    continue
                if "version" not in item:
                    continue
                if "sources" not in item:
                    continue
                for source in item["sources"]:
                    if "links" not in source:
                        continue

                    for entry in source["links"]:
                        if "url" not in entry:
                            continue
                        if entry["url"].endswith(variant) is False:
                            continue

                        models = []
                        if "devices" in item:
                            for device in item["devices"]:
                                _device = device
                                if "-" in device:
                                    _device = device.split("-")[0]
                                if _device  in models:
                                    continue
                                models.append(_device)

                        # Attempt to match macos_installer_handler.py's format
                        installers[item["build"]] = {
                            "Version":   item["version"],
                            "Build":     item["build"],
                            "Link":      entry["url"],
                            "Size":      -1,
                            "integrity": None,
                            "Source":    "AppleDB",
                            "Variant":   "Beta" if item["beta"] else "Public",
                            "OS":        os_data.os_conversion.os_to_kernel(item["version"] if " " not in item["version"] else item["version"].split(" ")[0]),
                            "Models":    models,
                            "Date":      item["released"],
                        }

        return installers


    def _main(self) -> None:
        """
        Main entry point
        """
        installers = {}
        apple_db_ipsw_installers = {}
        apple_db_pkg_installers = {}
        for build in self._supported_oses:
            installers.update(self._get_remote_installer_catalog(os_version=build))

        for installer in [".ipsw", "InstallAssistant.pkg"]:
            apple_db_items = self._get_apple_db_items(variant=installer)
            if installer == ".ipsw":
                apple_db_ipsw_installers = apple_db_items
            else:
                apple_db_pkg_installers = apple_db_items
            installers.update(apple_db_items)

        # Sort by name
        installers = dict(sorted(installers.items(), key=lambda item: item[1]["Build"]))

        print(f"Found {len(installers)} installers, checking which ones are missing")
        missing = []
        for build in installers:
            if self._does_file_exist(xnu_version=installers[build]["OS"], build=installers[build]["Build"], suffix=Path(installers[build]["Link"]).suffix) is True:
                continue
            missing.append(installers[build])

        print(f"Found {len(missing)} missing installers:" if missing else "No missing installers found")
        for installer in missing:
            print(f"  {Path(installer['Link']).suffix}: {installer['Version']} ({installer['Build']})")
            self._download_installer(installer)


        # Finally, fix names
        for apple_db_installers in [apple_db_ipsw_installers, apple_db_pkg_installers]:
            for installer in apple_db_installers:
                _build = apple_db_installers[installer]["Build"]
                _version = apple_db_installers[installer]["Version"]
                if _version.lower().endswith(" beta"):
                    _version += " 1"
                elif " " not in _version:
                    _version += " release"
                _base_name = f"{_version} ({_build})"

                for os in self._os_table:
                    for directory in [self._os_table[os], Path(self._os_table[os], "Dead URLs")]:
                        if not directory.exists():
                            continue
                        for file in directory.iterdir():
                            if file.is_dir():
                                continue
                            if f"({_build})" not in file.name and f" {_build} " not in file.name:
                                continue

                            _name = _base_name

                            _current_suffix = Path(file).suffix
                            if _current_suffix == ".pkg":
                                _name += " InstallAssistant.pkg"
                            elif _current_suffix == ".ipsw":
                                _name += " Restore.ipsw"
                            elif _current_suffix == ".integrityDataV1":
                                if Path(file).name.endswith(" Restore.ipsw.integrityDataV1"):
                                    _name += " Restore.ipsw.integrityDataV1"
                                elif Path(file).name.endswith("InstallAssistant.pkg.integrityDataV1"):
                                    _name += " InstallAssistant.pkg.integrityDataV1"
                                else:
                                    continue
                            else:
                                continue

                            if Path(file).name == _name:
                                continue

                            print(f"Renaming {file.name} to {_name}")
                            new_file_path = Path(directory, _name)
                            # -- SICHERHEITS-FIX: Native pathlib Methode verwenden ---
                            try:
                                file.replace(new_file_path) # Ersetzt mv
                                print(f"Moved {file.name} to {new_file_path}")
                            except OSError as e:
                                print(f"Failed to move {file} to {new_file_path}: {e}")
                            # ---------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="macOS Installer Backup")
    parser.
