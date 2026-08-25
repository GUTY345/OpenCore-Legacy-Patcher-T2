import os
import zipfile
import sys
import time
import argparse
import shutil
import subprocess
from pathlib import Path

# Fix: Force the execution directory immediately before importing local modules. 
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

# Import der internen Module
from ci_tooling.build_modules import (
    application,
    disk_images,
    package,
    sign_notarize
)

def extract_and_validate_tools():
    try:
        # Note: You are likely missing the code here that actually defined 
        # temp_dir, base_dir, and found_files before the cleanup happens!
        
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
# ... (rest of your script continues normally) ...
