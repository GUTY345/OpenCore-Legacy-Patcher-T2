"""
package.py: Generate packages (Installer, Uninstaller, AutoPkg-Assets)
"""

import os
from pathlib import Path
import tempfile
import macos_pkg_builder

from opencore_legacy_patcher import constants
from .package_scripts import GenerateScripts


class GeneratePackage:
    """
    Generate OpenCore-Patcher.pkg
    """

    def __init__(self) -> None:
        """
        Initialize
        """
        self._files = {
            "./dist/OpenCore-Patcher.app": "/Library/Application Support/Dortania/OpenCore-Patcher.app",
            "./ci_tooling/privileged_helper_tool/com.dortania.opencore-legacy-patcher.privileged-helper": "/Library/PrivilegedHelperTools/com.dortania.opencore-legacy-patcher.privileged-helper",
        }
        self._autopkg_files = {
            "./payloads/Launch Services/com.dortania.opencore-legacy-patcher.auto-patch.plist": "/Library/LaunchAgents/com.dortania.opencore-legacy-patcher.auto-patch.plist",
        }
        self._autopkg_files.update(self._files)


    def _generate_installer_welcome(self) -> str:
        """
        Generate Welcome message for installer PKG
        """
        _welcome = ""
        _welcome += "# Overview\n"
        _welcome += f"This package will install the OpenCore Legacy Patcher T2 application (v{constants.Constants().patcher_version}) on your system."
        _welcome += "\n\nOpenCore Legacy Patcher T2 will be installed in /Library/Application Support/Dortania."
        _welcome += "\n\nAdditionally, a shortcut for OpenCore Legacy Patcher T2 will be added in the '/Applications' folder."
        _welcome += "\n\nThis package will not 'Build and Install OpenCore' or install any 'Root Patches' on your machine. If required, you can run OpenCore Legacy Patcher T2 to install any patches you may need."
        _welcome += f"\n\nFor more information on OpenCore Legacy Patcher T2 usage, see our [documentation]({constants.Constants().guide_link}) and [GitHub repository]({constants.Constants().repo_link})."
        _welcome += "\n\n"
        _welcome += "## Files Installed"
        _welcome += "\n\nInstallation of this package will add the following files to your system:"
        for key, value in self._files.items():
            _welcome += f"\n\n- `{value}`"

        return _welcome


    def _generate_uninstaller_welcome(self) -> str:
        """
        Generate Welcome message for uninstaller PKG
        """
        _welcome = ""
        _welcome += "# Application Uninstaller\n"
        _welcome += "This package will uninstall the OpenCore Legacy Patcher T2 application and its Privileged Helper Tool from your system."
        _welcome += "\n\n"
        _welcome += "This will not remove any root patches or OpenCore configurations that you may have installed using OpenCore Legacy Patcher T2."
        _welcome += "\n\n"
        _welcome += f"For more information on OpenCore Legacy Patcher T2, see our [documentation]({constants.Constants().guide_link}) and [GitHub repository]({constants.Constants().repo_link})."

        return _welcome


    def _generate_autopkg_welcome(self) -> str:
        """
        Generate Welcome message for AutoPkg-Assets PKG
        """
        _welcome = ""
        _welcome += "# DO NOT RUN AUTOPKG-ASSETS MANUALLY!\n\n"
        _welcome += "## THIS CAN BREAK YOUR SYSTEM'S INSTALL!\n\n"
        _welcome += "This package should only ever be invoked by the Patcher itself, never downloaded or run by the user. Download the OpenCore-Patcher.pkg on the Github Repository.\n\n"
        _welcome += f"[OpenCore Legacy Patcher T2 GitHub Release]({constants.Constants().repo_link})"

        return _welcome


    def generate(self) -> None:
        """
        Generate OpenCore-Patcher.pkg
        """
        # --- 1. UNINSTALLER PKG GENERATION ---
        print("OpenCore-Patcher-Uninstaller.pkg generieren")
        print("Generating OpenCore-Patcher-Uninstaller.pkg")
        
        # Using a context manager ensures file descriptors close properly
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp_uninstall:
            tmp_uninstall.write(GenerateScripts().uninstall())
            tmp_uninstall_path = tmp_uninstall.name

        try:
            assert macos_pkg_builder.Packages(
                pkg_output="./dist/OpenCore-Patcher-Uninstaller.pkg",
                pkg_bundle_id="com.dortania.opencore-legacy-patcher-uninstaller",
                pkg_version=constants.Constants().patcher_version,
                pkg_background="./ci_tooling/pkg_assets/PkgBackground-Uninstaller.png",
                pkg_preinstall_script=tmp_uninstall_path,
                pkg_as_distribution=True,
                pkg_title="Uninstall OpenCore Legacy Patcher T2",
                pkg_welcome=self._generate_uninstaller_welcome(),
            ).build() is True
        finally:
            # Guarantees the temporary layout file is unlinked from /tmp/ when compilation finishes
            if os.path.exists(tmp_uninstall_path):
                os.unlink(tmp_uninstall_path)


        # --- 2. STANDARD INSTALLER PKG GENERATION ---
        print("OpenCore-Patcher.pkg generieren")
        print("Generating OpenCore-Patcher.pkg")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp_pre, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp_post:
            
            tmp_pre.write(GenerateScripts().preinstall_pkg())
            tmp_post.write(GenerateScripts().postinstall_pkg())
            
            tmp_pre_path = tmp_pre.name
            tmp_post_path = tmp_post.name

        try:
            assert macos_pkg_builder.Packages(
                pkg_output="./dist/OpenCore-Patcher.pkg",
                pkg_bundle_id="com.dortania.opencore-legacy-patcher",
                pkg_version=constants.Constants().patcher_version,
                pkg_allow_relocation=False,
                pkg_as_distribution=True,
                pkg_background="./ci_tooling/pkg_assets/PkgBackground-Installer.png",
                pkg_preinstall_script=tmp_pre_path,
                pkg_postinstall_script=tmp_post_path,
                pkg_file_structure=self._files,
                pkg_title="OpenCore Legacy Patcher T2",
                pkg_welcome=self._generate_installer_welcome(),
            ).build() is True
        finally:
            if os.path.exists(tmp_pre_path):
                os.unlink(tmp_pre_path)
            if os.path.exists(tmp_post_path):
                os.unlink(tmp_post_path)


        # --- 3. AUTOPKG ASSETS GENERATION ---
        print("AutoPkg-Assets.pkg generieren")
        print("Generating AutoPkg-Assets.pkg")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp_auto_pre, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp_auto_post:
            
            tmp_auto_pre.write(GenerateScripts().preinstall_autopkg())
            tmp_auto_post.write(GenerateScripts().postinstall_autopkg())
            
            tmp_auto_pre_path = tmp_auto_pre.name
            tmp_auto_post_path = tmp_auto_post.name

        try:
            assert macos_pkg_builder.Packages(
                pkg_output="./dist/AutoPkg-Assets.pkg",
                pkg_bundle_id="com.dortania.pkg.AutoPkg-Assets",
                pkg_version=constants.Constants().patcher_version,
                pkg_allow_relocation=False,
                pkg_as_distribution=True,
                pkg_background="./ci_tooling/pkg_assets/PkgBackground-AutoPkg.png",
                pkg_preinstall_script=tmp_auto_pre_path,
                pkg_postinstall_script=tmp_auto_post_path,
                pkg_file_structure=self._autopkg_files,
                pkg_title="AutoPkg Assets",
                pkg_welcome=self._generate_autopkg_welcome(),
            ).build() is True
        finally:
            if os.path.exists(tmp_auto_pre_path):
                os.unlink(tmp_auto_pre_path)
            if os.path.exists(tmp_auto_post_path):
                os.unlink(tmp_auto_post_path)
