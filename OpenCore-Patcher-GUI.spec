# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import time
import subprocess
from pathlib import Path

from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.osx import BUNDLE
from PyInstaller.building.build_main import Analysis

# Fix: Dynamically find the absolute path of the directory containing this spec file
SPEC_DIR = Path(__file__).parent.resolve()
sys.path.append(str(SPEC_DIR))

from opencore_legacy_patcher import constants

block_cipher = None

# Fix: Explicitly map the inputs using absolute paths to prevent CWD dependency issues
datas = [
   (str(SPEC_DIR / 'payloads.dmg'), '.'),
   (str(SPEC_DIR / 'Universal-Binaries.dmg'), '.'),
]

# Fix: Evaluate the existence of the internal resources DMG relative to the spec file
if (SPEC_DIR / "DortaniaInternalResources.dmg").exists():
   datas.append((str(SPEC_DIR / 'DortaniaInternalResources.dmg'), '.'))


a = Analysis([str(SPEC_DIR / 'OpenCore-Patcher-GUI.command')],
             pathex=[],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure,
          a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='OpenCore-Patcher',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch="universal2",  # Fix: Allows the app to run natively on both Intel and Apple Silicon Macs
          codesign_identity=None,
          entitlements_file=None)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='OpenCore-Patcher')

app = BUNDLE(coll,
             name='OpenCore-Patcher.app',
             icon=str(SPEC_DIR / "payloads/Icon/AppIcons/OC-Patcher.icns"), # Fix: Absolute path to the icon asset
             bundle_identifier="com.dortania.opencore-legacy-patcher",
             info_plist={
                "CFBundleName": "OpenCore Legacy Patcher",
                "CFBundleVersion": constants.Constants().patcher_version,
                "CFBundleShortVersionString": constants.Constants().patcher_version,
                "NSHumanReadableCopyright": constants.Constants().copyright_date,
                "LSMinimumSystemVersion": "10.13.6",
                "NSRequiresAquaSystemAppearance": False,
                "NSHighResolutionCapable": True,
                "Build Date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "BuildMachineOSBuild": subprocess.run(["/usr/bin/sw_vers", "-buildVersion"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode().strip(),
                "NSPrincipalClass": "NSApplication",
                "CFBundleIconName": "oclp",
             })
