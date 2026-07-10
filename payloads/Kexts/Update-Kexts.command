#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
import requests
import packaging.version
import tempfile

# Konfiguration der Kexts
KEXT_DICTIONARY = {
    "Acidanthera": {
        "AirportBrcmFixup": {"Repository": "https://github.com/acidanthera/AirportBrcmFixup", "Constants Variable": "self.airportbcrmfixup_version"},
        "BlueToolFixup": {"Repository": "https://github.com/acidanthera/BrcmPatchRAM", "Constants Variable": "self.bluetool_version", "Override": "BrcmPatchRAM"},
        "CPUFriend": {"Repository": "https://github.com/acidanthera/CPUFriend", "Constants Variable": "self.cpufriend_version"},
        "CryptexFixup": {"Repository": "https://github.com/acidanthera/CryptexFixup", "Constants Variable": "self.cryptexfixup_version"},
        "DebugEnhancer": {"Repository": "https://github.com/acidanthera/DebugEnhancer", "Constants Variable": "self.debugenhancer_version"},
        "FeatureUnlock": {"Repository": "https://github.com/acidanthera/FeatureUnlock", "Constants Variable": "self.featureunlock_version"},
        "Lilu": {"Repository": "https://github.com/acidanthera/Lilu", "Constants Variable": "self.lilu_version"},
        "NVMeFix": {"Repository": "https://github.com/acidanthera/NVMeFix", "Constants Variable": "self.nvmefix_version"},
        "RestrictEvents": {"Repository": "https://github.com/acidanthera/RestrictEvents", "Constants Variable": "self.restrictevents_version"},
        "RSRHelper": {"Repository": "https://github.com/khronokernel/RSRHelper", "Constants Variable": "self.rsrhelper_version"},
        "WhateverGreen": {"Repository": "https://github.com/acidanthera/WhateverGreen", "Constants Variable": "self.whatevergreen_version"},
    },
    "Misc": {
        "Innie": {"Repository": "https://github.com/cdf/Innie", "Constants Variable": "self.innie_version"},
    },
}

class GenerateKexts:
    def __init__(self):
        self.weg_version = None
        self.weg_old = None
        self.lilu_version = None
        self._set_cwd()
        self._iterate_over_kexts()
        self._special_kext_handling()

    def _set_cwd(self):
        os.chdir(Path(__file__).parent.absolute())

    def _special_kext_handling(self):
        if self.weg_version is None or self.lilu_version is None or self.weg_old is None:
            raise Exception("Unable to find latest WEG version!")
        if packaging.version.parse(self.weg_version) <= packaging.version.parse(self.weg_old):
            print("   WEG is up to date!")
            return

        print("Building modified WhateverGreen...")
        weg_source_url = f"https://github.com/acidanthera/WhateverGreen/archive/refs/tags/{self.weg_version}.zip"
        lilu_url = f"https://github.com/acidanthera/Lilu/releases/download/{self.lilu_version}/Lilu-{self.lilu_version}-DEBUG.zip"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download und Entpacken der Quellen
            for url in [weg_source_url, lilu_url]:
                subprocess.run(["/usr/bin/curl", "--location", url, "--output", f"{temp_dir}/{Path(url).name}"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            subprocess.run(["/usr/bin/unzip", "-q", f"{temp_dir}/WhateverGreen-{self.weg_version}.zip", "-d", temp_dir], check=True)
            subprocess.run(["/usr/bin/unzip", "-q", f"{temp_dir}/Lilu-{self.lilu_version}-DEBUG.zip", "-d", f"{temp_dir}/WhateverGreen-{self.weg_version}"], check=True)
            subprocess.run(["/usr/bin/git", "clone", "https://github.com/acidanthera/MacKernelSDK", f"{temp_dir}/WhateverGreen-{self.weg_version}/MacKernelSDK"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            patch_path = Path("./Acidanthera/WhateverGreen-Navi-Backlight.patch").absolute()
            subprocess.run(["/usr/bin/git", "apply", patch_path], check=True, cwd=f"{temp_dir}/WhateverGreen-{self.weg_version}")

            for variant in ["Release", "Debug"]:
                subprocess.run(["/usr/bin/xcodebuild", "-configuration", variant], cwd=f"{temp_dir}/WhateverGreen-{self.weg_version}", check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            for variant in ["RELEASE", "DEBUG"]:
                dst_path = Path(f"./Acidanthera/WhateverGreen-v{self.weg_version}-Navi-{variant}.zip").absolute()
                subprocess.run(["/usr/bin/zip", "-q", "-r", dst_path, "WhateverGreen.kext"], check=True, cwd=f"{temp_dir}/WhateverGreen-{self.weg_version}/build/{'Release' if variant == 'RELEASE' else 'Debug'}")
                old_path = Path(f"./Acidanthera/WhateverGreen-v{self.weg_old}-Navi-{variant}.zip")
                if old_path.exists(): old_path.unlink()

        self._update_constants_file("self.whatevergreen_navi_version", f"{self.weg_old}-Navi", f"{self.weg_version}-Navi")

    def _iterate_over_kexts(self):
        for kext_folder in KEXT_DICTIONARY:
            for kext_name in KEXT_DICTIONARY[kext_folder]:
                print(f"Checking {kext_name}...")
                override = KEXT_DICTIONARY[kext_folder][kext_name].get("Override")
                self._get_latest_release(kext_folder, kext_name, override_kext_zip_name=override)

    def _is_build_nightly(self, kext: str, version: str) -> bool:
        changelog_path = Path("../../CHANGELOG.md").absolute()
        if not changelog_path.exists(): return False
        with open(changelog_path, "r") as f:
            for line in f:
                if kext in line and version in line and ("rolling" in line or "nightly" in line):
                    return True
        return False

    def _get_latest_release(self, kext_folder, kext_name, override_kext_zip_name=None):
        repo_url = KEXT_DICTIONARY[kext_folder][kext_name]["Repository"].replace("https://github.com", "https://api.github.com/repos")
        latest_release = requests.get(f"{repo_url}/releases/latest").json()

        for variant in ["RELEASE", "DEBUG"]:
            if "tag_name" not in latest_release: continue
            remote_version = latest_release["tag_name"].lstrip("v")
            if kext_name == "WhateverGreen": self.weg_version = remote_version
            elif kext_name == "Lilu": self.lilu_version = remote_version

            local_version = self._get_local_version(kext_folder, kext_name, variant)
            if kext_name == "WhateverGreen": self.weg_old = local_version

            if packaging.version.parse(remote_version) <= packaging.version.parse(local_version):
                if not (remote_version == local_version and self._is_build_nightly(kext_name, local_version)): continue

            for asset in latest_release["assets"]:
                if asset["name"].endswith(f"{variant}.zip"):
                    print(f"  Downloading {kext_name} {variant}: v{remote_version}...")
                    zip_name = f"{override_kext_zip_name or kext_name}-v{remote_version}-{variant}.zip"
                    self._download_file(asset, f"./{kext_folder}/{zip_name}", f"{kext_name}.kext")
                    self._update_constants_file(KEXT_DICTIONARY[kext_folder][kext_name]["Constants Variable"], local_version, remote_version)
                    
                    if override_kext_zip_name:
                        os.rename(f"./{kext_folder}/{zip_name}", f"./{kext_folder}/{kext_name}-v{remote_version}-{variant}.zip")
                        old_zip = Path(f"./{kext_folder}/{kext_name}-v{local_version}-{variant}.zip")
                        if old_zip.exists(): old_zip.unlink()

    def _get_local_version(self, kext_folder, kext_name, variant):
        prefix, suffix = f"{kext_name}-v", f"-{variant}.zip"
        for file in Path(f"./{kext_folder}").iterdir():
            if file.name.startswith(prefix) and file.name.endswith(suffix):
                return file.name.replace(prefix, "").replace(suffix, "").lstrip("v")[:5]
        raise Exception(f"Could not find local version for {kext_name} {variant}")

    def _download_file(self, asset, file_path, file):
        # Sicherheitsprüfung: Download via HTTPS + Größenvergleich
        response = requests.get(asset["browser_download_url"], stream=True, timeout=30)
        response.raise_for_status()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_zip = f"{temp_dir}/temp.zip"
            with open(temp_zip, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Überprüfung der Dateigröße
            if os.path.getsize(temp_zip) != asset["size"]:
                raise Exception(f"SECURITY ALERT: Size mismatch for {file}!")

            # Log Audit
            with open("update_audit.log", "a") as log:
                log.write(f"Validated: {file} | Size: {asset['size']} | URL: {asset['browser_download_url']}\n")

            subprocess.run(["/usr/bin/unzip", "-q", temp_zip, "-d", temp_dir], check=True)
            subprocess.run(["/usr/bin/zip", "-q", "-r", Path(file_path).name, file], cwd=temp_dir, check=True)
            subprocess.run(["/bin/mv", f"{temp_dir}/{Path(file_path).name}", file_path], check=True)

    def _update_constants_file(self, variable_name, old_version, new_version):
        constants_file = Path("../../opencore_legacy_patcher/constants.py")
        content = constants_file.read_text().splitlines()
        new_content = []
        for line in content:
            if variable_name in line:
                new_content.append(line.replace(old_version, new_version))
            else:
                new_content.append(line)
        constants_file.write_text("\n".join(new_content))

if __name__ == '__main__':
    GenerateKexts()
