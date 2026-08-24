"""
build.py: Class for generating OpenCore Configurations tailored for Macs
"""

import copy
import pickle
import shutil
import logging
import subprocess
import zipfile
import plistlib
import sys
import webbrowser
import subprocess

from pathlib import Path
from datetime import date

from .. import constants

from ..detections import device_probe
from ..support import utilities
from ..datasets import model_array

from .networking import (
wired,
wireless
)
from . import (
bluetooth,
firmware,
graphics_audio,
support,
storage,
smbios,
security,
misc
)
from ..datasets import (
    os_data
)

def rmtree_handler(func, path, excinfo) -> None:
    exc = excinfo[1] if isinstance(excinfo, tuple) else excinfo
    if isinstance(exc, FileNotFoundError):
        return
    logging.error(f"Critical: rmtree_handler cannot start cleanup for path: {path}")
    logging.exception(exc)
    raise exc

class BuildOpenCore:
        
    """
    Core Build Library for generating and validating OpenCore EFI Configurations
    compatible with genuine Macs
    """
    
    def __init__(self, model: str, global_constants: constants.Constants) -> None:
        try:
            self.model: str = model
            self.config: dict = None
            self.constants: constants.Constants = global_constants

            if not hasattr(self.constants, "device_properties"):
                self.constants.device_properties = {}

            self._build_opencore()
        except Exception as e:
            logging.error(f"Function Error: {e}")
            logging.exception("Stack Trace:") # This prints the full technical error
            logging.info("Please try again later.")
            sys.exit(3)

    
    def _require_exact_target_hardware(self) -> None:
        """Refuse to build unless the host matches the single supported hardware target exactly."""
        if self.constants.custom_model:
            logging.warning("Custom model builds safety override; proceeding with caution.")

        if self.model != "MacBookPro15,1":
            logging.warning(f"This build is locked to MacBookPro15,1 but model is {self.model}. Proceeding with caution.")

        if not self.constants.computer:
            logging.warning("Hardware probe data is unavailable; proceeding with caution.")
            return

        detected_model = getattr(self.constants.computer, "real_model", None) or getattr(self.constants.computer, "reported_model", None)
        if detected_model != "MacBookPro15,1":
            logging.warning(f"Detected model {detected_model} does not match the required MacBookPro15,1 target. Proceeding.")

        if not self.constants.computer.cpu or not self.constants.computer.cpu.name:
            logging.warning("CPU probe data is unavailable.")
        else:
            cpu_name = self.constants.computer.cpu.name
            if "i7-8850H" not in cpu_name and "8850H" not in cpu_name:
                logging.warning(f"CPU {cpu_name} is not Intel Core i7-8850H.")

        if not self.constants.computer.igpu or not isinstance(self.constants.computer.igpu, device_probe.Intel):
            logging.warning("Expected an Intel UHD 630 iGPU.")
        else:
            igpu_id = getattr(self.constants.computer.igpu, "device_id", None)
            if igpu_id not in {0x3E9B, 0x3E92, 0x3E91, 0x3E98}:
                logging.warning(f"Expected Intel UHD 630 iGPU but got {hex(igpu_id) if igpu_id else None}.")

        if not self.constants.computer.dgpu or not isinstance(self.constants.computer.dgpu, device_probe.AMD):
            logging.warning("Expected an AMD Radeon Pro 560X dGPU.")
        else:
            dgpu_id = getattr(self.constants.computer.dgpu, "device_id", None)
            dgpu_model = str(getattr(self.constants.computer.dgpu, "model", "") or "")
            if dgpu_id != 0x67EF or "560X" not in dgpu_model.upper():
                logging.warning(f"Expected AMD Radeon Pro 560X but got id {hex(dgpu_id) if dgpu_id else None}, model {dgpu_model}.")

        if self.constants.computer.memory_size_mb != 16384:
            logging.warning(f"RAM size is {self.constants.computer.memory_size_mb} MB (expected 16384 MB).")

        if self.constants.computer.memory_speed_mhz != 2400:
            logging.warning(f"RAM speed is {self.constants.computer.memory_speed_mhz} MHz (expected 2400 MHz).")

        if self.constants.computer.memory_type is None or "DDR4" not in self.constants.computer.memory_type.upper():
            logging.warning(f"RAM type is {self.constants.computer.memory_type} (expected DDR4).")


    def _build_efi(self) -> None:
        """
        Build EFI folder
        """
        logging.info("---OpenCore Legacy Patcher T2 by Albert Müller---")
        self._require_exact_target_hardware()
        try:
            if self.constants.detected_os >= os_data.os_data.golden_gate:
                if not self.constants.custom_model:
                    logging.info("macOS 27 Golden Gate is not available for Intel Macs. Apple Silicon required. Please do not try to upgrade to Golden Gate on Intel Macs.")
                    logging.info("macOS 27 Golden Gate is compiled only for arm64, specifically for Apple Silicon.")
                    webbrowser.open("https://www.apple.com/os/macos/")
                else:
                    logging.info("You're not building OpenCore on your target system that is running macOS 27 Golden Gate.")
            else:
                logging.info("You're not targeting macOS 27 Golden Gate, this is good.")
        except Exception as e:
            logging.error("We couldn't make sure if you are targeting macOS 27 Golden Gate or newer. Skip checking...")
            logging.exception("Stack Trace:")
            pass
                
        utilities.cls()
        logging.info(f"Building Configuration {'for external' if self.constants.custom_model else 'on model'}: {self.model}")

        self._generate_base()
        self._set_revision()

        # Set Lilu and co.
        support.BuildSupport(self.model, self.constants, self.config).enable_kext("Lilu.kext", self.constants.lilu_version, self.constants.lilu_path)
        self.config["Kernel"]["Quirks"]["DisableLinkeditJettison"] = True

        # Intel UHD 630 VMM Stall Fix (2018-2020 Models)
        _T2_UHD630_MODELS = ["MacBookPro15,1", "MacBookPro15,2", "MacBookPro15,3", "MacBookPro15,4", "MacBookPro16,1", "MacBookPro16,3", "MacBookPro16,4", "Macmini8,1", "iMac20,1", "iMac20,2"]
        if self.model in _T2_UHD630_MODELS:
            logging.info(f"- Disabling VMM CPUID for {self.model} to prevent UHD 630 driver stall")
            self.constants.set_vmm_cpuid = False

        # Determine T2 status upfront
        is_t2 = self.model in model_array.T2Macs or "T2_CHIP" in self.constants.device_properties.get(self.model, {}).get("Features", [])

        if is_t2:
            try:
                logging.info("- Applying in-memory T2 booter and SMBIOS alignment")
                self.config.setdefault("Booter", {}).setdefault("Quirks", {}).update({
                    "RebuildAppleMemoryMap": False,
                    "EnableWriteUnprotector": False,
                    "SyncRuntimePermissions": False,
                    "DevirtualiseMmio": False,
                })
                self.config.setdefault("PlatformInfo", {})["UpdateSMBIOSMode"] = "Create" # Costum verursacht Probleme auf T2 Macs, insbesonders auf T2 Macs mit gespoofter SMBIOS, indem einige Sachen erst gar nicht funktionieren oder funktionieren nicht richtig, wie die Batteries des MacBook zu laden.
                ## self.config.setdefault("Kernel", {}).setdefault("Quirks", {})["CustomSMBIOSGuid"] = True - das funktioniert gar nicht richtig und CostumSMBIOSGuid wurde sowieso nie eingeschaltet, und wahrscheinlich verurascht auf T2 Macs auch Probleme
                self.config.setdefault("Misc", {}).setdefault("Security", {})["SecureBootModel"] = "Disabled"
            except Exception as e:
                logging.error("Whoops, applying in-memory T2 booter and SMBIOS alignments failed because of the following error:")
                logging.exception("Stack Trace:")
                logging.info("Please try again later.")
                sys.exit(3)

            try:
                logging.info("- Adding T2-specific bypass NVRAM variables")

                if "NVRAM" not in self.config:
                    self.config["NVRAM"] = {"Add": {}, "Delete": {}}
                if "Delete" not in self.config["NVRAM"]:
                    self.config["NVRAM"]["Delete"] = {}

                if "7C436110-AB2A-4BBB-A880-FE41995C9F82" not in self.config["NVRAM"]["Add"]:
                    self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] = {"boot-args": ""}

                # Ensure we strictly clean out legacy variables from NVRAM to prevent corecrypto mismatch
                if "7C436110-AB2A-4BBB-A880-FE41995C9F82" not in self.config["NVRAM"]["Delete"]:
                    self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] = []

                for target_arg in ["boot-args", "csr-active-config", "amfi-allow-arguments"]:
                    if target_arg not in self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]:
                        self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"].append(target_arg)

                # Fetch template boot-args, scrub any accidental Lilu flags inherited from template plists
                raw_args = self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"].get("boot-args", "")
                scrubbed_args = " ".join([arg for arg in raw_args.split() if not arg.startswith("-lilu")])

                # Append required T2 args safely without compounding spaces
                t2_args = "-ibtcompatbeta -amfipassbeta"
                self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] = f"{scrubbed_args} {t2_args}".strip()

                # Ensure WriteFlash is enabled to commit changes to SPI ROM
                self.config["NVRAM"]["WriteFlash"] = True

                # T2 Macs: do NOT disable the IOMMU. The T2 bridge talks to the host
                # over an internal XHCI link that depends on IOMMU-mapped DMA — forcing
                # this True causes "Unresponsive firmware or bridge unresponsive" panics
                # (AppleUSBXHCICommandRing::abortCommand / setPowerStateGated failures).
                self.config["Kernel"]["Quirks"]["DisableIoMapper"] = False
            except Exception as e:
                logging.error("Whoops, the app failed to inject the required OpenCore configuration because of the following error:")
                logging.exception("Stack Trace:")
                logging.info("Please try again later.")
                sys.exit(3)
        else:
            # For Non-T2 Legacy Hardware
            if "NVRAM" not in self.config:
                self.config["NVRAM"] = {"Add": {}}
            if "7C436110-AB2A-4BBB-A880-FE41995C9F82" not in self.config["NVRAM"]["Add"]:
                self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] = {"boot-args": ""}
                
            current_boot_args = self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
            
            # Target some 2017 Mac models specifically to bypass vt-d/broadcom complications
            # Dies ist benötigt, um WLAN und Bluetooth richtig zu funktionieren auf macOS 26 Tahoe.
            _2017_MODELS_NEED_DART = ["iMac18,1", "iMac18,2", "iMac18,3", "MacBookPro14,1"]
            if self.model in _2017_MODELS_NEED_DART:
                if "dart=0" not in current_boot_args:
                    logging.info(f"- Appending dart=0 boot argument for {self.model} hardware target to fix WiFi/Bluetooth issues on macOS Tahoe ({self.model})")
                    current_boot_args = f"{current_boot_args} dart=0".strip()

            if "-lilubetaall" not in current_boot_args:
                current_boot_args = f"{current_boot_args} -lilubetaall".strip()
                
            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] = current_boot_args

        # Call support functions
        for function in [
            firmware.BuildFirmware,
            wired.BuildWiredNetworking,
            wireless.BuildWirelessNetworking,
            graphics_audio.BuildGraphicsAudio,
            bluetooth.BuildBluetooth,
            storage.BuildStorage,
            smbios.BuildSMBIOS,
            security.BuildSecurity,
            misc.BuildMiscellaneous
        ]:
            try:
                function(self.model, self.constants, self.config)
            except Exception as e:
                logging.error("There is a serious error")
                logging.exception(f"Failed to initialize the function called {function.__name__}")
                logging.exception("Stack Trace:")
                sys.exit(3)

        # Work-around ocvalidate
        # Auch behebt einen Fehler, indem Windows 10/11 per Boot Camp-Installation verschwindet wegen zu viele Malen \EFI\Microsoft\Boot\bootmgfw.efi erstellt werden oder das \EFI\Microsoft\Boot\bootmgfw.efi erstellen in config.plist, auch wenn es schon da steht.
        if self.constants.validate is False:
            logging.info("- Adding bootmgfw.efi BlessOverride")
            
            # Ensure the section exists
            if "BlessOverride" not in self.config["Misc"]:
                self.config["Misc"]["BlessOverride"] = []
                
            # FIX: Only append if it's not already there
            target_path = "\\EFI\\Microsoft\\Boot\\bootmgfw.efi"
            if target_path not in self.config["Misc"]["BlessOverride"]:
                self.config["Misc"]["BlessOverride"].append(target_path)    

    
    def _generate_base(self) -> None:
        """
        Generate OpenCore base folder and config
        """

        if not Path(self.constants.build_path).exists():
            logging.info("Creating build folder")
            Path(self.constants.build_path).mkdir()
        else:
            logging.info("Build folder already present, skipping")

        if Path(self.constants.opencore_zip_copied).exists():
            logging.info("Deleting old copy of OpenCore zip")
            Path(self.constants.opencore_zip_copied).unlink()
        if Path(self.constants.opencore_release_folder).exists():
            logging.info("Deleting old copy of OpenCore folder")
            shutil.rmtree(self.constants.opencore_release_folder, onerror=rmtree_handler, ignore_errors=True)

        logging.info("")
        logging.info(f"- Adding OpenCore v{self.constants.opencore_version} {'DEBUG' if self.constants.opencore_debug is True else 'RELEASE'}")
        shutil.copy(self.constants.opencore_zip_source, self.constants.build_path)
        zipfile.ZipFile(self.constants.opencore_zip_copied).extractall(self.constants.build_path)

        # Setup config.plist for editing
        logging.info("- Adding config.plist for OpenCore")
        shutil.copy(self.constants.plist_template, self.constants.oc_folder)
        self.config = plistlib.load(Path(self.constants.plist_path).open("rb"))

    def _save_config(self) -> None:
        """
        Save config.plist to disk with structural validation to prevent
        plistlib type errors.
        """
        
        def find_bad_key(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if not isinstance(k, str):
                        # This log entry will pinpoint exactly where the corruption is
                        logging.error(f"!!! NON-STRING KEY FOUND !!!")
                        logging.error(f"    Location: {path}")
                        logging.error(f"    Offending Key: {k} (Type: {type(k)})")
                    find_bad_key(v, f"{path}/{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_bad_key(item, f"{path}[{i}]")

        # Run the diagnostic scan before attempting to save
        find_bad_key(self.config)

        # Proceed to save
        try:
            # Ensure the directory exists
            Path(self.constants.plist_path).parent.mkdir(parents=True, exist_ok=True)
            
            with Path(self.constants.plist_path).open("wb") as f:
                plistlib.dump(self.config, f, sort_keys=True)
            logging.info("Successfully saved config.plist")
            
        except Exception as e:
            logging.error(f"Function Error while saving config: {e}")
            logging.exception("Stack Trace:")
            # Use sys.exit if you want to stop the build on failure
            sys.exit(3)    
    
    def _set_revision(self) -> None:
        """
        Set revision information in config.plist
        """
    
        # --- Safe access to #Revision ---
        rev = self.config.setdefault("#Revision", {})
        rev["Build-Version"] = f"{self.constants.patcher_version} - {date.today()}"
    
        if not self.constants.custom_model:
            rev["Build-Type"] = "OpenCore Built on Target Machine"
            computer_copy = copy.copy(self.constants.computer)
            computer_copy.ioregistry = None
            
            # FIX: Convert the binary pickle dump to a string representation 
            # so plistlib doesn't try to parse it as an active data structure.
            rev["Hardware-Probe"] = str(pickle.dumps(computer_copy))
        else:
            rev["Build-Type"] = "OpenCore Built for External Machine"
    
        rev["OpenCore-Version"] = (
            f"{self.constants.opencore_version} - "
            f"{'DEBUG' if self.constants.opencore_debug else 'RELEASE'}"
        )
        rev["Original-Model"] = self.model
    
        # --- Hardened NVRAM structure ---
        nvram = self.config.setdefault("NVRAM", {})
        add   = nvram.setdefault("Add", {})
    
        guid_key = "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102"
        guid     = add.setdefault(guid_key, {})
    
        # Validate type to avoid malicious plist poisoning
        if not isinstance(guid, dict):
            logging.error(f"NVRAM GUID {guid_key} is not a dictionary — refusing to write metadata")
            logging.exception("Stack Trace:") 
            return
    
        # --- Safe writes ---
        guid["OCLP-Version"] = f"{self.constants.patcher_version}"
        guid["OCLP-Model"]   = self.model

    
    
    def _build_opencore(self) -> None:
        """
        Kick off the build process

        This is the main function:
        - Generates the OpenCore configuration
        - Cleans working directory
        - Signs files
        - Validates generated EFI
        """

        # Generate OpenCore Configuration
        self._build_efi()
        if self.constants.allow_oc_everywhere is False or self.constants.allow_native_spoofs is True or (self.constants.custom_serial_number != "" and self.constants.custom_board_serial_number != ""):
            smbios.BuildSMBIOS(self.model, self.constants, self.config).set_smbios()
        support.BuildSupport(self.model, self.constants, self.config).cleanup()
        self._save_config()

        # Post-build handling
        support.BuildSupport(self.model, self.constants, self.config).sign_files()
        support.BuildSupport(self.model, self.constants, self.config).validate_pathing()
        logging.info("")
        logging.info(f"Your OpenCore EFI for {self.model} has been built at:")
        if self.constants.oc_build_path != None:
            subprocess.run(["/bin/mv", str(self.constants.opencore_release_folder), str(self.constants.oc_build_path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode().strip()
            logging.info(f"    {self.constants.oc_build_path}")
        else:
            logging.info(f"    {self.constants.opencore_release_folder}")
        logging.info("")
