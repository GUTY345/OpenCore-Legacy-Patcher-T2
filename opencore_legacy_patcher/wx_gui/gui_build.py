"""
gui_build.py: Generate UI for Building OpenCore
"""

import wx
import logging
import threading
import traceback
import time
import webbrowser
import wx.html2
import markdown2
import urllib.parse

from .. import constants

from ..efi_builder import build

from ..wx_gui import (
    gui_main_menu,
    gui_install_oc,
    gui_support
)

class BuildFrame(wx.Frame):
    """
    Create a frame for building OpenCore
    Uses a Modal Dialog for smoother transition from other frames
    """
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None, **kwargs) -> None:
        logging.info("Initializing Build Frame")
        super(BuildFrame, self).__init__(parent, title=title, size=(350, 200), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
        
        self.install = kwargs.get("install", False)
        self.save = kwargs.get("save", False)
        gui_support.GenerateMenubar(self, global_constants).generate()

        self.build_successful: bool = False

        self.install_button: wx.Button = None
        self.text_box:     wx.TextCtrl = None
        self.frame_modal:    wx.Dialog = None

        self.constants: constants.Constants = global_constants
        self.title: str = title
        self.stock_output = logging.getLogger().handlers[0].stream

        self.frame_modal = wx.Dialog(self, title=title, size=(400, 200))

        self._generate_elements(self.frame_modal)

        if self.constants.update_stage != gui_support.AutoUpdateStages.INACTIVE:
            self.constants.update_stage = gui_support.AutoUpdateStages.BUILDING

        self.Centre()
        self.frame_modal.ShowWindowModal()

        if not self.constants.Developer_Mode:
            self._invoke_build()


    def on_build_failure(self) -> None:
        """
        Standard error dialog for build failure.
        """
        dlg = wx.MessageDialog(
            self,
            "An error occurred while building OpenCore.\n\nPlease check the logs in the text box for more information.",
            "Build Error",
            style=wx.OK | wx.ICON_ERROR
        )
        dlg.ShowModal()
        dlg.Destroy()
    
    def _generate_elements(self, frame: wx.Frame = None) -> None:
        """
        Generate UI elements for build frame

        Format:
            - Title label:        Build and Install OpenCore
            - Text:               Model: {Build or Host Model}
            - Profile selection:  Radio buttons (MBP14,3 only)
            - Button:             Install OpenCore
            - Read-only text box: {empty}
            - Button:             Return to Main Menu
        """
        frame = self if not frame else frame

        title_label = wx.StaticText(frame, label="Build and Install OpenCore", pos=(-1,5))
        title_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)

        model_label = wx.StaticText(frame, label=f"Model: {self.constants.custom_model or self.constants.computer.real_model}", pos=(-1,30))
        model_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        model_label.Centre(wx.HORIZONTAL)

        next_y = model_label.GetPosition()[1] + model_label.GetSize()[1] + 5

        # Profile selection for MacBookPro14,3
        target_model = self.constants.custom_model or self.constants.computer.real_model
        if target_model == "MacBookPro14,3":
            self.radio_standard = wx.RadioButton(frame, label="STANDARD / SAFE", pos=(-1, next_y), style=wx.RB_GROUP)
            self.radio_standard.Centre(wx.HORIZONTAL)
            next_y += 30

            self.radio_testa = wx.RadioButton(frame, label="TEST-A (GPU)", pos=(-1, next_y))
            self.radio_testa.Centre(wx.HORIZONTAL)
            next_y += 30

            self.radio_testb = wx.RadioButton(frame, label="TEST-B (GPU + No-Compat)", pos=(-1, next_y))
            self.radio_testb.Centre(wx.HORIZONTAL)
            next_y += 30
            
            self.radio_testc = wx.RadioButton(frame, label="TEST-C (GPU + No-Compat + VBootArgs)", pos=(-1, next_y))
            self.radio_testc.Centre(wx.HORIZONTAL)
            next_y += 40
            
            if self.constants.build_profile == "test_c":
                self.radio_testc.SetValue(True)
            elif self.constants.build_profile == "test_b":
                self.radio_testb.SetValue(True)
            elif self.constants.build_profile == "test_a":
                self.radio_testa.SetValue(True)
            else:
                self.radio_standard.SetValue(True)
        else:
            self.radio_standard = None
            self.radio_testa = None
            self.radio_testb = None
            self.radio_testc = None

        if self.constants.Developer_Mode:
            # Button: Build OpenCore (Only in Developer Mode to allow selection)
            build_button = wx.Button(frame, label="🔨 Build OpenCore", pos=(-1, next_y), size=(150, 30))
            build_button.Bind(wx.EVT_BUTTON, self.on_build_click)
            build_button.Centre(wx.HORIZONTAL)
            self.build_button = build_button
            next_y += 35

        # Button: Install OpenCore
        install_button = wx.Button(frame, label="🔩 Install OpenCore", pos=(-1, next_y), size=(150, 30))
        install_button.Bind(wx.EVT_BUTTON, self.on_install)
        install_button.Centre(wx.HORIZONTAL)
        install_button.Disable()
        self.install_button = install_button

        # Read-only text box: {empty}
        text_box = wx.TextCtrl(frame, value="", pos=(-1, install_button.GetPosition()[1] + install_button.GetSize()[1] + 10), size=(380, 350), style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2)
        text_box.Centre(wx.HORIZONTAL)
        self.text_box = text_box

        # Button: Return to Main Menu
        return_button = wx.Button(frame, label="Return to Main Menu", pos=(-1, text_box.GetPosition()[1] + text_box.GetSize()[1] + 10), size=(150, 30))
        return_button.Bind(wx.EVT_BUTTON, self.on_return_to_main_menu)
        return_button.Centre(wx.HORIZONTAL)
        
        # Disable by default if standard mode (since it builds automatically)
        if not self.constants.Developer_Mode:
            return_button.Disable()
            
        self.return_button = return_button

        # Adjust window size to fit all elements
        frame.SetSize((-1, return_button.GetPosition()[1] + return_button.GetSize()[1] + 40))


    def _invoke_build(self) -> None:
        """
        Invokes build function and waits for it to finish
        """
        while gui_support.PayloadMount(self.constants, self).is_unpack_finished() is False:
            wx.Yield()
            time.sleep(self.constants.thread_sleep_interval)

        thread = threading.Thread(target=self._build)
        thread.start()

        gui_support.wait_for_thread(thread)

        self.return_button.Enable()

        # Check if config.plist was built
        if self.build_successful is False:
            self.on_build_failure()
            return
        else:
            if getattr(self, "install", False):
                self.on_install()
            elif getattr(self, "save", False):
                dialog = wx.MessageDialog(
                    parent=self,
                    message=f"OpenCore has been built and saved to:\n{self.constants.oc_build_path}",
                    caption="Save Successful",
                    style=wx.OK | wx.ICON_INFORMATION
                )
                dialog.ShowModal()
                self.frame_modal.Destroy()
            else:
                dialog = wx.MessageDialog(
                    parent=self,
                    message=f"Would you like to install OpenCore now?",
                    caption="Finished building your OpenCore configuration!",
                    style=wx.YES_NO | wx.ICON_QUESTION
                )
                dialog.SetYesNoLabels("Install to disk", "View build log")
                
                self.on_install() if dialog.ShowModal() == wx.ID_YES else self.install_button.Enable()


    def _build(self) -> None:
        """
        Calls build function and redirects stdout to the text box
        """
        logger = logging.getLogger()
        handler = gui_support.ThreadHandler(self.text_box) # Keep a reference
        logger.addHandler(handler)


        if self.constants.build_profile == "test_b":
            profile_name = "TEST-B GPU"
        elif self.constants.build_profile == "test_c":
            profile_name = "TEST-C TAHOE / ALBERT"
        elif self.constants.build_profile == "test_c_spoofed":
            profile_name = "TEST-C SPOOFED / ALBERT"
        else:
            profile_name = "STANDARD / SAFE"
        target_model = self.constants.custom_model or self.constants.computer.real_model

        logging.info("=========================================")
        logging.info("          BUILD CONFIGURATION            ")
        logging.info("=========================================")
        logging.info(f"Target Model: {target_model}")
        logging.info(f"Profile: {profile_name}")

        if target_model == "MacBookPro14,3":
            t1_status = "DETECTED" if getattr(self.constants.computer, 't1_chip', False) else "ENABLED (MBP14,3)"
            wifi_status = f"{self.constants.computer.wifi.vendor_id:04X}:{self.constants.computer.wifi.device_id:04X}" if getattr(self.constants.computer, 'wifi', None) else "14E4:43BA"
            logging.info(f"T1 Security:  {t1_status}")
            logging.info(f"Wi-Fi Module: {wifi_status}")

        logging.info("=========================================")
        logging.info("")


        try:
            build.BuildOpenCore(self.constants.custom_model or self.constants.computer.real_model, self.constants)
            self.build_successful = True
        except Exception as e:
            logging.error("An internal error occurred while building:\n")
            logging.error(traceback.format_exc())
        finally:
            # Ensure we ALWAYS remove the handler before the thread exits
            logger.removeHandler(handler)

            # Handle bug from 2.1.0 where None type was stored in config.plist from global settings
            if "TypeError: unsupported type: <class 'NoneType'>" in traceback.format_exc():
                logging.error("If you continue to see this error, delete the following file and restart the application:")
                logging.error("Path: /Users/Shared/.com.dortania.opencore-legacy-patcher.plist")

        if len(logger.handlers) > 2:
            logger.removeHandler(logger.handlers[2])


    def on_return_to_main_menu(self, event: wx.Event = None) -> None:
        """
        Return to main menu
        """
        self.frame_modal.Close()
        main_menu_frame = gui_main_menu.MainFrame(
            None,
            title=self.title,
            global_constants=self.constants,
            screen_location=self.GetScreenPosition()
        )
        main_menu_frame.Show()
        self.frame_modal.Destroy()
        self.Destroy()
        
    def on_build_click(self, event: wx.Event) -> None:
        self.build_button.Disable()
        if getattr(self, "radio_standard", None):
            self.radio_standard.Disable()
            self.radio_testa.Disable()
            self.radio_testb.Disable()
            self.radio_testc.Disable()
        if hasattr(self, "return_button"):
            self.return_button.Disable()
        self._invoke_build()

    def on_install(self, event: wx.Event = None) -> None:
        """
        Launch install frame
        """
        # Stop any pending UI updates
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            if isinstance(handler, gui_support.ThreadHandler):
                logger.removeHandler(handler)
        
        self.frame_modal.Hide() # Hide first to feel responsive
        self.frame_modal.Destroy()
        self.Destroy()
        install_oc_frame = gui_install_oc.InstallOCFrame(
            None,
            title=self.title,
            global_constants=self.constants,
            screen_location=self.GetScreenPosition()
        )
        install_oc_frame.Show()


