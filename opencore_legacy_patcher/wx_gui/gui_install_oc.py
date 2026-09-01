"""
gui_install_oc.py: Frame for installing OpenCore to disk
"""

import wx
import logging
import threading
import traceback
import webbrowser
import platform
import time
import sys

from .. import constants

from ..datasets import os_data, model_array
from ..support import install

from ..wx_gui import (
    gui_main_menu,
    gui_support,
    gui_sys_patch_display
)

class InstallOCFrame(wx.Frame):
    """
    Create a frame for installing OpenCore to disk
    """
    
    def get_mac_version():
        # platform.mac_ver() returns a tuple like ('13.4.1', ('', '', ''), 'arm64')
        os_version_str = platform.mac_ver()[0]
        
        if not os_version_str:
            return (0, 0) # Not a macOS system
            
        # Convert '13.4.1' into an integer tuple: (13, 4, 1)
        return tuple(map(int, os_version_str.split('.')))
    
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None):
        logging.info("Initializing Install OpenCore Frame")
        super(InstallOCFrame, self).__init__(parent, title=title, size=(300, 120), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
        gui_support.GenerateMenubar(self, global_constants).generate()

        self.constants: constants.Constants = global_constants
        self.title: str = title
        self.result: bool = False

        self.available_disks: dict = None
        self.stock_output = logging.getLogger().handlers[0].stream

        self.progress_bar_animation: gui_support.GaugePulseCallback = None

        self.hyperlink_colour = (25, 179, 231)

        self._generate_elements()

        if self.constants.update_stage != gui_support.AutoUpdateStages.INACTIVE:
            self.constants.update_stage = gui_support.AutoUpdateStages.INSTALLING

        self.Centre()
        self.Show()

        self._display_disks()


    def _generate_elements(self) -> None:
        """
        Display indeterminate progress bar while collecting disk information
        """
        # Title label: Install OpenCore
        title_label = wx.StaticText(self, label="Install OpenCore", pos=(-1,5))
        title_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)

        # Text: Parsing local disks...
        text_label = wx.StaticText(self, label="Fetching information on local disks...", pos=(-1,30))
        text_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        text_label.Centre(wx.HORIZONTAL)
        self.text_label = text_label

        # Progress bar: {indeterminate}
        progress_bar = wx.Gauge(self, range=100, pos=(-1, text_label.GetPosition()[1] + text_label.GetSize()[1]), size=(150, 30), style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        progress_bar.Centre(wx.HORIZONTAL)

        progress_bar_animation = gui_support.GaugePulseCallback(self.constants, progress_bar)
        progress_bar_animation.start_pulse()

        self.progress_bar_animation = progress_bar_animation
        self.progress_bar = progress_bar


    def _fetch_disks(self) -> None:
        """
        Fetch information on local disks safely using local scoping 
        to prevent race conditions and dictionary manipulation.
        """
        raw_disks = install.tui_disk_installation(self.constants).list_disks()
        if not raw_disks:
            self.available_disks = {}
            return

        current_version = InstallOCFrame.get_mac_version()

        if current_version < (10, 12):
            logging.info(f"Detected legacy macOS version {current_version}. Cleaning up output safely...")
            
            ignore = ["disk image", "read-only", "virtual"]
            filtered_disks = {}
            
            for disk_id, disk_info in raw_disks.items():
                disk_name = disk_info.get('name', '').lower()
                if not any(bad_string in disk_name for bad_string in ignore):
                    filtered_disks[disk_id] = disk_info
            
            self.available_disks = filtered_disks
        else:
            logging.info(f"Detected macOS {current_version}. No legacy cleanup required.")
            self.available_disks = raw_disks


    def _display_disks(self) -> None:
        """
        Display disk selection dialog
        """
        thread = threading.Thread(target=self._fetch_disks)
        thread.start()

        gui_support.wait_for_thread(thread)

        self.progress_bar_animation.stop_pulse()
        self.progress_bar.Hide()

        # Create wxDialog for disk selection
        dialog = wx.Dialog(self, title=self.title, size=(380, -1))

        # Title label: Install OpenCore
        title_label = wx.StaticText(dialog, label="Install OpenCore", pos=(-1,5))
        title_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)

        # Text: select disk to install OpenCore onto
        text_label = wx.StaticText(dialog, label="Select disk to install OpenCore onto:", pos=(-1, title_label.GetPosition()[1] + title_label.GetSize()[1] + 5))
        text_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        text_label.Centre(wx.HORIZONTAL)

        # Add note: "Missing disks? Ensure they're FAT32 or formatted as GUID/GPT"
        gpt_note = wx.StaticText(dialog, label="Missing disks? Ensure they're FAT32 or formatted as GUID/GPT", pos=(-1, text_label.GetPosition()[1] + text_label.GetSize()[1] + 5))
        gpt_note.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
        gpt_note.Centre(wx.HORIZONTAL)

        if self.available_disks:
            disk_root = self.constants.booted_oc_disk if self.constants.custom_model is None else None
            if disk_root:
                disk_root = self.constants.booted_oc_disk.strip("disk")
                disk_root = "disk" + disk_root.split("s")[0]
                logging.info(f"Checking if booted disk is present: {disk_root}")

            items = len(self.available_disks)
            longest_label = max((len(self.available_disks[disk]['disk']) + len(self.available_disks[disk]['name']) + len(str(self.available_disks[disk]['size']))) for disk in self.available_disks)
            longest_label = longest_label * 9
            spacer = 0
            logging.info("Available disks:")
            for disk in self.available_disks:
                logging.info(f"- {self.available_disks[disk]['disk']} - {self.available_disks[disk]['name']} - {self.available_disks[disk]['size']}")
                disk_button = wx.Button(dialog, label=f"{self.available_disks[disk]['disk']} - {self.available_disks[disk]['name']} - {self.available_disks[disk]['size']}", size=(longest_label ,30), pos=(-1, gpt_note.GetPosition()[1] + gpt_note.GetSize()[1] + 5 + spacer))
                disk_button.Centre(wx.HORIZONTAL)
                disk_button.Bind(wx.EVT_BUTTON, lambda event, disk=disk: self._display_volumes(disk, self.available_disks))
                if disk_root == self.available_disks[disk]['disk'] or items == 1:
                    disk_button.SetDefault()
                spacer += 25

            if disk_root:
                disk_label = wx.StaticText(dialog, label="Note: Blue represent the disk OpenCore is currently booted from", pos=(-1, disk_button.GetPosition()[1] + disk_button.GetSize()[1] + 5))
                disk_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
                disk_label.Centre(wx.HORIZONTAL)
            else:
                disk_label = wx.StaticText(dialog, label="", pos=(-1, disk_button.GetPosition()[1] + 15))
                disk_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
        else:
            disk_label = wx.StaticText(dialog, label="Failed to find any applicable disks", pos=(-1, gpt_note.GetPosition()[1] + gpt_note.GetSize()[1] + 5))
            disk_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_BOLD))
            disk_label.Centre(wx.HORIZONTAL)

        search_button = wx.Button(dialog, label="Search for disks again", size=(150,30), pos=(-1, disk_label.GetPosition()[1] + disk_label.GetSize()[1] + 5))
        search_button.Centre(wx.HORIZONTAL)
        search_button.Bind(wx.EVT_BUTTON, self.on_reload_frame)

        return_button = wx.Button(dialog, label="Return to Main Menu", size=(150,30), pos=(-1, search_button.GetPosition()[1] + 20))
        return_button.Centre(wx.HORIZONTAL)
        return_button.Bind(wx.EVT_BUTTON, self.on_return_to_main_menu)

        dialog.SetSize((-1, return_button.GetPosition()[1] + return_button.GetSize()[1] + 40))
        dialog.ShowWindowModal()
        self.dialog = dialog


    def _display_volumes(self, disk: str, dataset: dict) -> None:
        """
        List volumes on disk
        """
        self.dialog.Close()

        dialog = wx.Dialog(
            self,
            title=f"Volumes on {disk}",
            style=wx.CAPTION | wx.CLOSE_BOX,
            size=(300, 300)
        )

        text_label = wx.StaticText(dialog, label=f"Volumes on {disk}", pos=(-1, 10))
        text_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        text_label.Centre(wx.HORIZONTAL)

        partitions = install.tui_disk_installation(self.constants).list_partitions(disk, dataset)
        items = len(partitions)
        longest_label = max((len(partitions[partition]['partition']) + len(partitions[partition]['name']) + len(str(partitions[partition]['size']))) for partition in partitions)
        longest_label = longest_label * 10
        spacer = 0
        logging.info(f"Available partitions for {disk}:")
        for partition in partitions:
            logging.info(f"- {partitions[partition]['partition']} - {partitions[partition]['name']} - {partitions[partition]['size']}")
            disk_button = wx.Button(dialog, label=f"{partitions[partition]['partition']} - {partitions[partition]['name']} - {partitions[partition]['size']}", size=(longest_label,30), pos=(-1, text_label.GetPosition()[1] + text_label.GetSize()[1] + 5 + spacer))
            disk_button.Centre(wx.HORIZONTAL)
            disk_button.Bind(wx.EVT_BUTTON, lambda event, partition=partition: self._install_oc_process(partition))
            if items == 1 or self.constants.booted_oc_disk == partitions[partition]['partition']:
                disk_button.SetDefault()
            spacer += 25

        return_button = wx.Button(dialog, label="Return to Main Menu", size=(150,30), pos=(-1, disk_button.GetPosition()[1] + disk_button.GetSize()[1]))
        return_button.Centre(wx.HORIZONTAL)
        return_button.Bind(wx.EVT_BUTTON, self.on_return_to_main_menu)

        dialog.SetSize((-1, return_button.GetPosition()[1] + return_button.GetSize()[1] + 40))
        dialog.ShowWindowModal()
        self.dialog = dialog


    def _install_oc_process(self, partition: dict) -> None:
        """
        Install OpenCore to disk
        """
        self.dialog.Close()

        dialog = wx.Dialog(
            self,
            title=f"Installing OpenCore to {partition}",
            style=wx.CAPTION | wx.CLOSE_BOX,
            size=(370, 200)
        )

        text_label = wx.StaticText(dialog, label=f"Installing OpenCore to {partition}", pos=(-1, 10))
        text_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        text_label.Centre(wx.HORIZONTAL)

        text_box = wx.TextCtrl(dialog, value="", pos=(-1, text_label.GetPosition()[1] + text_label.GetSize()[1] + 10), size=(350, 200), style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2)
        text_box.Centre(wx.HORIZONTAL)
        self.text_box = text_box

        return_button = wx.Button(dialog, label="Return to Main Menu", size=(150,30), pos=(-1, text_box.GetPosition()[1] + text_box.GetSize()[1] + 10))
        return_button.Centre(wx.HORIZONTAL)
        return_button.Bind(wx.EVT_BUTTON, self.on_return_to_main_menu)
        return_button.Disable()

        dialog.SetSize((370, return_button.GetPosition()[1] + return_button.GetSize()[1] + 40))
        dialog.ShowWindowModal()
        self.dialog = dialog

        self._invoke_install_oc(partition)
        return_button.Enable()


    def _invoke_install_oc(self, partition: dict) -> None:
        """
        Invoke OpenCore installation
        """
        thread = threading.Thread(target=self._install_oc, args=(partition,))
        thread.start()

        gui_support.wait_for_thread(thread)

        if self.result is True:
            if self.constants.update_stage != gui_support.AutoUpdateStages.INACTIVE and self.constants.detected_os >= os_data.os_data.big_sur:
                self.constants.update_stage = gui_support.AutoUpdateStages.ROOT_PATCHING
                popup_message = wx.MessageDialog(
                    self,
                    f"OpenCore has finished installing to disk.\n\nWould you like to update your root patches next?", "Success",
                    wx.YES_NO | wx.YES_DEFAULT
                )
                popup_message.ShowModal()
                if popup_message.GetReturnCode() == wx.ID_YES:
                    self.Hide()
                    gui_sys_patch_display.SysPatchDisplayFrame(
                        parent=None,
                        title=self.title,
                        global_constants=self.constants,
                        screen_location=self.GetPosition()
                    )
                    self.Destroy()
                return

            elif not self.constants.custom_model:
                if self.constants.computer.real_model in model_array.T2Macs:
                    url = "https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2-Instructions-for-T2-Macs/tree/main"
                    webbrowser.open(url)
                gui_support.RestartHost(self).restart(message="OpenCore has finished installing to disk.\n\nYou will need to reboot and hold the Option key and select OpenCore/Boot EFI's option.\n\nWould you like to reboot?\n\nIn some cases, instead of OpenCore it is labeled as Windows on T2 Macs if you\n\nare running Boot Camp on your Mac.")
            else:
                popup_message = wx.MessageDialog(
                    self,
                    f"OpenCore has finished installing to disk.\n\nYou can eject the drive, insert it into the {self.constants.custom_model}, reboot, hold the Option key and select OpenCore/Boot EFI's option.", "Success",
                    wx.OK
                )
                popup_message.ShowModal()
        else:
            if self.constants.update_stage != gui_support.AutoUpdateStages.INACTIVE:
                self.constants.update_stage = gui_support.AutoUpdateStages.FINISHED
            
            try:
                error_dialog = wx.Dialog(self, title="Installation Error", size=(460, 200))
                
                main_sizer = wx.BoxSizer(wx.VERTICAL)
                button_sizer = wx.BoxSizer(wx.HORIZONTAL)
                
                error_msg = "OpenCore installation failed.\n\nWould you like to report this issue or ask Gemini for help?"
                msg_text = wx.StaticText(error_dialog, label=error_msg)
                msg_text.SetFont(gui_support.font_factory(12, wx.FONTWEIGHT_NORMAL))
                
                btn_report = wx.Button(error_dialog, id=wx.ID_OK, label="Report Issue")
                btn_gemini = wx.Button(error_dialog, id=wx.ID_ANY, label="Ask Gemini")
                btn_close  = wx.Button(error_dialog, id=wx.ID_CANCEL, label="Close")
                
                # Define a custom return code identifier for Gemini tracking
                GEMINI_CLICKED_ID = 10001
                
                # Bind an event so clicking the button closes the dialog and returns our custom identifier
                error_dialog.Bind(wx.EVT_BUTTON, lambda event: error_dialog.EndModal(GEMINI_CLICKED_ID), btn_gemini)
                
                main_sizer.Add(msg_text, 1, wx.ALL | wx.EXPAND, 20)
                button_sizer.Add(btn_report, 0, wx.RIGHT, 10)
                button_sizer.Add(btn_gemini, 0, wx.RIGHT, 10)
                button_sizer.Add(btn_close, 0)
                
                main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM | wx.RIGHT, 20)
                
                error_dialog.SetSizer(main_sizer)
                error_dialog.Layout()
                error_dialog.Centre()
                
                response = error_dialog.ShowModal()
                
                if response == wx.ID_OK:
                    webbrowser.open("https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2/issues")
                
                # Check directly for your custom event return hook code
                # Unter macOS Catalina und älter Gemini funktioniert nicht richtig unter Safari/WebKit
                elif response == GEMINI_CLICKED_ID:
                    if self.constants.detected_os >= os_data.os_data.big_sur:
                        logging.info("- Launching Gemini AI Assistant (wx.html2 WebView)")
                        gemini_window = gui_support.GeminiWebView(self, title="Gemini AI Assistant")
                        gemini_window.Show()
                    else:
                        logging.info("- Launching Gemini AI Assistant (default web browser, host predates Big Sur)")
                        logging.info("macOS Catalina, Mojave and High Sierra can't load Gemini in Safari and WebKit because they're too old.")
                        webbrowser.open("https://gemini.google.com")
                    
                error_dialog.Destroy()

            except Exception as ui_error:
                logging.error("An invalid syntax prevented from displaying the error. The error is the following:")
                logging.exception("Stack Trace:")
                logging.info("Please report this issue.")
                logging.info("To fix this bug, please check for updates and update as soon as the next release is out.")
                print("\n" + "="*50)
                print(f"CRITICAL UI ERROR CAUGHT: {ui_error}")
                print(traceback.format_exc())
                print("="*50 + "\n")
                time.sleep(90)
                sys.exit(3)
            except Exception as ui_error:
                logging.error("An invalid syntax prevented from displaying the error. The error is the following:")
                logging.exception("Stack Trace:")
                logging.info("Please report this issue.")
                logging.info("To fix this bug, please check for updates and update as soon as the next release is out.")
                print("\n" + "="*50)
                print(f"CRITICAL UI ERROR CAUGHT: {ui_error}")
                print(traceback.format_exc())
                print("="*50 + "\n")
                time.sleep(90)
                sys.exit(3)

    def _install_oc(self, partition: dict) -> None:
        """
        Install OpenCore to disk safely
        """
        logging.info(f"Installing OpenCore to {partition}")

        logger = logging.getLogger()
        my_handler = gui_support.ThreadHandler(self.text_box)
        logger.addHandler(my_handler)

        try:
            # FIX: Capture the boolean return value from the backend.
            # Do not assume execution was successful just because no unhandled exception crashed Python.
            install_success = install.tui_disk_installation(self.constants).install_opencore(partition)
            
            if install_success:
                self.result = True
                logging.info("OpenCore transfer complete")
            else:
                self.result = False
                logging.error("Installation failed during internal file copy or mount routines.")
        
        except Exception as e:
            self.result = False
            logging.error(f"Installation encountered a critical error: {e}")
            logging.error(traceback.format_exc())
        
        finally:
            if my_handler in logger.handlers:
                logger.removeHandler(my_handler)

    def on_reload_frame(self, event: wx.Event = None) -> None:
        self.Destroy()
        frame = InstallOCFrame(
            None,
            title=self.title,
            global_constants=self.constants,
            screen_location=self.GetScreenPosition()
        )
        frame.Show()


    def on_return_to_main_menu(self, event: wx.Event = None) -> None:
        main_menu_frame = gui_main_menu.MainFrame(
            None,
            title=self.title,
            global_constants=self.constants,
            screen_location=self.GetScreenPosition()
        )
        main_menu_frame.Show()
        self.Destroy()
