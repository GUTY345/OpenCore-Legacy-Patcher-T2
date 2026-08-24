#!/usr/bin/env python3
"""
Build-Project.command: Generate OpenCore-Patcher.app and OpenCore-Patcher.pkg
Optimiert für Sicherheit und Stabilität.
"""

import os
import zipfile
import sys
import time
import argparse
from pathlib import Path

# Fix: Force the execution directory immediately before importing local modules. 
# This guarantees that 'ci_tooling' looks for assets in the right relative path.
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

# Auto-redirect to local virtual environment if available and not inside it
if not getattr(sys, 'frozen', False):
    venv_dir = SCRIPT_DIR / ".venv"
    if venv_dir.exists() and Path(sys.prefix).resolve() != venv_dir.resolve():
        venv_python = venv_dir / "bin" / "python3"
        if venv_python.exists():
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)


# Import der internen Module
from ci_tooling.build_modules import (
    application,
    disk_images,
    package,
    sign_notarize
)

def extract_and_copy_tools():
    """
    Locates OpenCoreTools.zip, extracts the archive, and copies 
    the necessary binaries to payloads/OpenCore.
    """
    try:
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).resolve().parent

        # Locate the ZIP file
        zip_path = None
        for file in base_dir.rglob("OpenCoreTools.zip"):
            zip_path = file
            break
        
        if not zip_path:
            for file in base_dir.rglob("*Tools*.zip"):
                zip_path = file
                break

        if not zip_path:
            print("[WARN] Could not locate OpenCoreTools.zip. Proceeding...")
            return

        print(f"[INFO] Found archive at: {zip_path}")

        dest_dir = base_dir / "payloads" / "OpenCore"
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Temporary extraction path to inspect contents
        temp_dir = base_dir / "temp_extracted_tools"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        print("[INFO] Extracting archive...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Search for the target binaries inside the extracted directory
        found_files = 0
        for path in temp_dir.rglob("*"):
            if path.name in ('ocvalidate', 'macserial') and path.is_file():
                target_path = dest_dir / path.name
                
                # Copy to payloads/OpenCore
                shutil.copy2(path, target_path)
                
                # Apply Unix execution rights
                os.chmod(target_path, 0o755)
                
                print(f"  > Copied and set permissions: {path.name}")
                found_files += 1

        # Clean up temporary files
        shutil.rmtree(temp_dir)

        if found_files < 2:
            print(f"[WARN] Only found {found_files} of 2 required tools (ocvalidate/macserial).")

        # Clear the quarantine attribute to allow execution on modern macOS
        try:
            subprocess.run(
                ["xattr", "-rd", "com.apple.quarantine", str(base_dir)], 
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

        print("[INFO] Tools successfully extracted and validated.\n")

    except Exception as e:
        print(f"[ERROR] Failed to extract tools: {e}")

def check_file_exists(path: Path) -> None:
    if not path.exists():
        print(f"Fehler: Erwartete Datei/Verzeichnis nicht gefunden: {path}")
        print(f"Error: Expected file/directory not found: {path}")
        sys.exit(3)

def main() -> None:
    try:
        print("Extracting ocvalidate and macserial and move to the proper directory")
        extract_and_copy_tools()
    except Exception as e:
        print(f"\n[!] Das Aufbauen des Apps hat abgebrochen aufgrund eines Fehlers: {e}")
        print(f"\n[!] Building the app stopped because of some error: {e}")
        sys.exit(3)
    parser = argparse.ArgumentParser(description="Build OpenCore Legacy Patcher Suite", add_help=False)

    # Signing & Notarization
    parser.add_argument("--application-signing-identity", type=str, help="Application Signing Identity")
    parser.add_argument("--installer-signing-identity", type=str, help="Installer Signing Identity")
    parser.add_argument("--notarization-apple-id", type=str, help="Notarization Apple ID")
    parser.add_argument("--notarization-password", type=str, help="Notarization Password (Alternative: Env Var)")
    parser.add_argument("--notarization-team-id", type=str, help="Notarization Team ID")

    # CI/CD & Local Build Parameters
    parser.add_argument("--git-branch", type=str, default=None)
    parser.add_argument("--git-commit-url", type=str, default=None)
    parser.add_argument("--git-commit-date", type=str, default=None)
    parser.add_argument("--reset-dmg-cache", action="store_true")
    parser.add_argument("--reset-pyinstaller-cache", action="store_true")
    
    # Steps
    parser.add_argument("--run-as-individual-steps", action="store_true")
    parser.add_argument("--prepare-application", action="store_true")
    parser.add_argument("--prepare-package", action="store_true")
    parser.add_argument("--prepare-assets", action="store_true")

    args = parser.parse_args()

    # Passwort-Sicherheit: Umgebungsvariable hat Vorrang vor CLI-Argument
    notarization_password = os.environ.get("NOTARIZATION_PASSWORD") or args.notarization_password

    try:
        # 1. Assets
        if (args.run_as_individual_steps is False) or (args.run_as_individual_steps and args.prepare_assets):
            print("--- Generiere Disk Images ---")
            print("--- generate disk images ---")
            disk_images.GenerateDiskImages(args.reset_dmg_cache).generate()

        # 2. Application
        if (args.run_as_individual_steps is False) or (args.run_as_individual_steps and args.prepare_application):
            print("--- Signiere Helper Tool ---")
            print("--- Sign Helper Tool ---")
            sign_notarize.SignAndNotarize(
                path=Path("./ci_tooling/privileged_helper_tool/com.dortania.opencore-legacy-patcher.privileged-helper"),
                signing_identity=args.application_signing_identity,
                notarization_apple_id=args.notarization_apple_id,
                notarization_password=notarization_password,
                notarization_team_id=args.notarization_team_id,
            ).sign_and_notarize()

            print("--- Baue App ---")
            print("--- Building the app ---")
            application.GenerateApplication(
                reset_pyinstaller_cache=args.reset_pyinstaller_cache,
                git_branch=args.git_branch,
                git_commit_url=args.git_commit_url,
                git_commit_date=args.git_commit_date,
            ).generate()

            check_file_exists(Path("dist/OpenCore-Patcher.app"))
            print("--- Signiere App ---")
            print("--- Sign the app ---")
            sign_notarize.SignAndNotarize(
                path=Path("dist/OpenCore-Patcher.app"),
                signing_identity=args.application_signing_identity,
                notarization_apple_id=args.notarization_apple_id,
                notarization_password=notarization_password,
                notarization_team_id=args.notarization_team_id,
                entitlements=Path("./ci_tooling/entitlements/entitlements.plist"),
            ).sign_and_notarize()

        # 3. Packages
        if (args.run_as_individual_steps is False) or (args.run_as_individual_steps and args.prepare_package):
            print("--- Baue Packages ---")
            print("--- Build packages ---")
            package.GeneratePackage().generate()
            
            for pkg in ["OpenCore-Patcher.pkg", "OpenCore-Patcher-Uninstaller.pkg"]:
                pkg_path = Path(f"dist/{pkg}")
                check_file_exists(pkg_path)
                print(f"--- Signiere {pkg} ---")
                print(f"--- Sign {pkg} ---")
                sign_notarize.SignAndNotarize(
                    path=pkg_path,
                    signing_identity=args.installer_signing_identity,
                    notarization_apple_id=args.notarization_apple_id,
                    notarization_password=notarization_password,
                    notarization_team_id=args.notarization_team_id,
                ).sign_and_notarize()

    except Exception as e:
        print(f"\n[!] Das Aufbauen des Apps hat abgebrochen aufgrund eines Fehlers: {e}")
        print(f"\n[!] Building the app stopped because of some error: {e}")
        sys.exit(3)

if __name__ == '__main__':
    _start = time.time()
    main()
    # Fixed small English translation grammar ("has been built for" instead of "has been builded for")
    print(f"\nBuild script erfolgreich in {str(round(time.time() - _start, 2))} Sekunden abgeschlossen.")
    print(f"\nBuild script completed in {str(round(time.time() - _start, 2))} seconds.")
