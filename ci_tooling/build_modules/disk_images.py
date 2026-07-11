"""
disk_images.py: Fetch and generate disk images (Universal-Binaries.dmg, payloads.dmg)
"""

import os
import shutil
import subprocess
from pathlib import Path

from opencore_legacy_patcher import constants
from opencore_legacy_patcher.support import subprocess_wrapper


class GenerateDiskImages:

    def __init__(self, reset_dmg_cache: bool = False) -> None:
        """
        Initialize
        """
        self.reset_dmg_cache = reset_dmg_cache

    def _delete_extra_binaries(self) -> None:
        """
        Delete extra binaries from payloads directory natively.
        """
        whitelist_folders = {
            "ACPI",
            "Config",
            "Drivers",
            "Icon",
            "Kexts",
            "OpenCore",
            "Tools",
            "Launch Services",
        }

        whitelist_files = set()

        print("Extra Binärdateien löschen...")
        print("Deleting extra binaries...")
        payloads_dir = Path("payloads")
        
        if not payloads_dir.exists():
            print("- 'payloads' directory does not exist, skipping cleanup.")
            return

        for file in payloads_dir.glob("*"):
            if file.is_dir():
                if file.name in whitelist_folders:
                    continue
                print(f"- Verzeichnis löschen: {file.name}")
                print(f"- Deleting directory: {file.name}")
                shutil.rmtree(file)  # Safe, native recursive deletion
            else:
                if file.name in whitelist_files:
                    continue
                print(f"- Deleting file: {file.name}")
                file.unlink()  # Safe, native file deletion

    def _generate_payloads_dmg(self) -> None:
        """
        Generate disk image containing all payloads
        Disk image will be password protected due to issues with
        Apple's notarization system and inclusion of kernel extensions
        """
        dmg_path = Path("./payloads.dmg")

        if dmg_path.exists():
            if not self.reset_dmg_cache:
                print("- payloads.dmg already exists, skipping creation")
                return

            print("- Removing old payloads.dmg")
            dmg_path.unlink(missing_ok=True)

        print("DMG generieren...")
        print("Generating DMG...")
        
        # Hardcoded password tokenized cleanly without shell risk
        # Note: In production, consider pulling 'password' from an environment variable
        dmg_password = os.environ.get("DMG_PASSWORD", "password")

        subprocess_wrapper.run_and_verify([
            '/usr/bin/hdiutil', 'create', str(dmg_path),
            '-megabytes', '32000',
            '-format', 'UDZO', '-ov',
            '-volname', 'OpenCore Patcher Resources (Base)',
            '-fs', 'HFS+',
            '-layout', 'NONE',
            '-srcfolder', './payloads',
            '-passphrase', dmg_password, '-encryption'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        print("DMG generation complete")

    def _download_resources(self) -> None:
        """
        Download required dependencies securely
        """
        patcher_support_pkg_version = constants.Constants().patcher_support_pkg_version
        required_resources = [
            "Universal-Binaries.dmg"
        ]

        print("Downloading required resources...")
        for resource in required_resources:
            # Strictly validate the resource string to prevent directory traversal
            # e.g., resource = "../../etc/passwd" or unexpected inputs
            resource_path = Path(resource).name
            target_path = Path(".") / resource_path

            if target_path.exists():
                if self.reset_dmg_cache:
                    print(f"  - Removing old {resource_path}")
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()
                else:
                    print(f"- {resource_path} existiert bereits, Herunterladen wird übersprungen")
                    print(f"- {resource_path} already exists, skipping download")
                    continue

            print(f"- Herunterladen von {resource_path}...")
            print(f"- Downloading {resource_path}...")

            # Clean URL building, strictly mapping to the safe filename
            download_url = f"https://github.com/dortania/PatcherSupportPkg/releases/download/{patcher_support_pkg_version}/{resource_path}"

            subprocess_wrapper.run_and_verify(
                [
                    "/usr/bin/curl", "-fLo", str(target_path),
                    download_url
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            if not target_path.exists():
                print(f"- {resource_path} nicht gefunden nach dem Herunterladen")
                print(f"- {resource_path} not found after download")
                raise FileNotFoundError(f"{resource_path} failed to download.")
                sys.exit(3)

    def generate(self) -> None:
        """
        Generate disk images
        """
        self._delete_extra_binaries()
        self._generate_payloads_dmg()
        self._download_resources()
