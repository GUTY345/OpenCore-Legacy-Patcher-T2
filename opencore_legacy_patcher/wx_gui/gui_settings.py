"""
gui_settings.py: Settings Frame for the GUI
"""

import wx
import pprint
import logging
import os
import sys
from pathlib import Path
from .. import constants


from ..wx_gui import (
    gui_support,
    gui_update
)
from ..support import (
    global_settings,
    network_handler,
    analytics_handler
)
from ..datasets import (
    smbios_data,
    os_data
)


class SettingsFrame(wx.Frame):
    """
    Modal-based Settings Frame
    """
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None):
        logging.info("Initializing Settings Frame")
        self.constants: constants.Constants = global_constants
        self.title: str = title
        self.parent: wx.Frame = parent

        self.hyperlink_colour = (25, 179, 231)

        self.settings = self._settings()

        self.frame_modal = wx.Dialog(parent, title=title, size=(600, 685))
        self._generate_elements(self.frame_modal)
        self.frame_modal.ShowWindowModal()

    def _generate_elements(self, frame: wx.Frame = None) -> None:
        """
        Generates elements for the Settings Frame
        Uses wx.Notebook to implement a tabbed interface
        and relies on 'self._settings()' for populating
        """

        notebook = wx.Notebook(frame)
        notebook.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(10)

        tabs = list(self.settings.keys())
        if not self.constants.Developer_Mode:
            tabs.remove("Developer")
        for tab in tabs:
            panel = wx.ScrolledWindow(notebook)
            panel.SetScrollRate(0, 20)
            notebook.AddPage(panel, tab)

        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Add return button
        return_button = wx.Button(frame, label="Return", pos=(-1, -1), size=(100, 30))
        return_button.Bind(wx.EVT_BUTTON, self.on_return)
        return_button.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        sizer.Add(return_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        frame.SetSizer(sizer)

        horizontal_center = frame.GetSize()[0] / 2
        for tab in tabs:
            if tab not in self.settings:
                continue

            stock_height = 0
            stock_width = 20

            height = stock_height
            width = stock_width

            lowest_height_reached = height
            highest_height_reached = height

            panel = notebook.GetPage(tabs.index(tab))

            for setting, setting_info in self.settings[tab].items():
                if setting_info["type"] == "populate":
                    # execute populate function
                    if setting_info["args"] == wx.Frame:
                        setting_info["function"](panel)
                    else:
                        raise Exception("Invalid populate function")
                    continue

                if setting_info["type"] == "title":
                    stock_height = lowest_height_reached
                    height = stock_height
                    width = stock_width

                    height += 10

                    # Add title
                    title = wx.StaticText(panel, label=setting, pos=(-1, -1))
                    title.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))

                    title.SetPosition((int(horizontal_center) - int(title.GetSize()[0] / 2) - 15, height))
                    highest_height_reached = height + title.GetSize()[1] + 10
                    height += title.GetSize()[1] + 10
                    continue

                if setting_info["type"] == "sub_title":
                    # Add sub-title
                    sub_title = wx.StaticText(panel, label=setting, pos=(-1, -1))
                    sub_title.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))

                    sub_title.SetPosition((int(horizontal_center) - int(sub_title.GetSize()[0] / 2) - 15, height))
                    highest_height_reached = height + sub_title.GetSize()[1] + 10
                    height += sub_title.GetSize()[1] + 10
                    continue

                if setting_info["type"] == "wrap_around":
                    height = highest_height_reached
                    width = 300 if width is stock_width else stock_width
                    continue

                if setting_info["type"] == "checkbox":
                    # Add checkbox, and description underneath
                    checkbox = wx.CheckBox(panel, label=setting, pos=(10 + width, 10 + height), size = (300,-1))

                    value = False
                    if "value" in setting_info:
                        try:
                            value = bool(setting_info["value"])
                        except ValueError:
                            logging.error(f"Invalid value for {setting}, got {setting_info['value']} (type: {type(setting_info['value'])})")
                            value = False

                    checkbox.SetValue(value)
                    checkbox.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_BOLD))
                    event = lambda event, warning=setting_info["warning"] if "warning" in setting_info else "", override=bool(setting_info["override_function"]) if "override_function" in setting_info else False: self.on_checkbox(event, warning, override)
                    checkbox.Bind(wx.EVT_CHECKBOX, event)
                    if "condition" in setting_info:
                        checkbox.Enable(setting_info["condition"])
                        if setting_info["condition"] is False:
                            checkbox.SetValue(False)

                elif setting_info["type"] == "spinctrl":
                    # Add spinctrl, and description underneath
                    spinctrl = wx.SpinCtrl(panel, value=str(setting_info["value"]), pos=(width - 20, 10 + height), min=setting_info["min"], max=setting_info["max"], size = (45,-1))
                    spinctrl.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_BOLD))
                    spinctrl.Bind(wx.EVT_TEXT, lambda event, variable=setting: self.on_spinctrl(event, variable))
                    # Add label next to spinctrl
                    label = wx.StaticText(panel, label=setting, pos=(spinctrl.GetSize()[0] + width - 16, spinctrl.GetPosition()[1]))
                    label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_BOLD))
                elif setting_info["type"] == "choice":
                    # Title
                    title = wx.StaticText(panel, label=setting, pos=(width + 30, 10 + height))
                    title.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_BOLD))
                    height += title.GetSize()[1] + 10

                    # Add combobox, and description underneath
                    choice = wx.Choice(panel, pos=(width + 25, 10 + height), choices=setting_info["choices"], size = (150,-1))
                    choice.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
                    choice.SetSelection(choice.FindString(setting_info["value"]))
                    if "override_function" in setting_info:
                        choice.Bind(wx.EVT_CHOICE, lambda event, variable=setting: self.settings[tab][variable]["override_function"](event))
                    else:
                        choice.Bind(wx.EVT_CHOICE, lambda event, variable=setting: self.on_choice(event, variable))
                    height += 10
                elif setting_info["type"] == "button":
                    button = wx.Button(panel, label=setting, pos=(width + 25, 10 + height), size = (200,-1))
                    button.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
                    button.Bind(wx.EVT_BUTTON, lambda event, variable=setting: self.settings[tab][variable]["function"](event))
                    height += 10

                else:
                    raise Exception("Invalid setting type")

                lines = '\n'.join(setting_info["description"])
                description = wx.StaticText(panel, label=lines, pos=(30 + width, 10 + height + 20))
                description.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
                height += 40
                if "condition" in setting_info:
                    if setting_info["condition"] is False:
                        description.SetForegroundColour((128, 128, 128))

                # Check number of lines in description, and adjust spacer accordingly
                for i, line in enumerate(lines.split('\n')):
                    if line == "":
                        continue
                    if i == 0:
                        height += 11
                    else:
                        height += 13

                if height > lowest_height_reached:
                    lowest_height_reached = height


    def _settings(self) -> dict:
        """
        Generates a dictionary of settings to be used in the GUI
        General format:
        {
            "Tab Name": {
                "type": "title" | "checkbox" | "spinctrl" | "populate" | "wrap_around",
                "value": bool | int | str,
                "variable": str,  (Variable name)
                "constants_variable": str, (Constants variable name, if different from "variable")
                "description": [str, str, str], (List of strings)
                "warning": str, (Optional) (Warning message to be displayed when checkbox is checked)
                "override_function": function, (Optional) (Function to be executed when checkbox is checked)
            }
        }
        """

        models = [model for model in smbios_data.smbios_dictionary if "_" not in model and " " not in model and smbios_data.smbios_dictionary[model]["Board ID"] is not None]
        socketed_imac_models = ["iMac9,1", "iMac10,1", "iMac11,1", "iMac11,2", "iMac11,3", "iMac12,1", "iMac12,2"]
        socketed_gpu_models = socketed_imac_models + ["MacPro3,1", "MacPro4,1", "MacPro5,1", "Xserve2,1", "Xserve3,1"]

        settings = {
            "App": {
                "General": {
                    "type": "title",
                },
                "wrap_around 1": {
                    "type": "wrap_around",
                },
                "Allow Reporting": {
                    "type": "checkbox",
                    "value": global_settings.GlobalEnviromentSettings().read_property("EnableCrashAndAnalyticsReporting"),
                    "variable": "EnableCrashAndAnalyticsReporting",
                    "description": [
                        "When disabled, patcher will not",
                        "report any info to Dortania.",
                    ],
                    "override_function": self._update_global_settings,
                    "condition": not analytics_handler.ANALYTICS_SERVER and analytics_handler.SITE_KEY == None
                },
                "Remove Unused KDKs": {
                    "type": "checkbox",
                    "value": global_settings.GlobalEnviromentSettings().read_property("ShouldNukeKDKs") or self.constants.should_nuke_kdks,
                    "variable": "ShouldNukeKDKs",
                    "constants_variable": "should_nuke_kdks",
                    "description": [
                        "When enabled, the app will remove",
                        "unused Kernel Debug Kits from the system",
                        "during root patching.",
                    ],
                    "override_function": self._update_global_settings,
                },
            },
            "Statistics": {
                "Statistics": {
                    "type": "title",
                },
                "Populate Stats": {
                    "type": "populate",
                    "function": self._populate_app_stats,
                    "args": wx.Frame,
                },
            },
            "Developer": {
                "Validation": {
                    "type": "title",
                },
                "Trigger Exception": {
                    "type": "button",
                    "function": self.on_test_exception,
                    "description": [
                    ],
                },
                "Misc": {
                    "type": "title",
                },
                "Default OpenCore Build": {
                    "type": "choice",
                    "choices": [
                        "💬 Ask Each Time",
                        "🟢 Standard / Safe Build",
                        "🧪 [LEVEL-B] Experimental GPU",
                        "🧪 [LEVEL-C] Experimental Tahoe (Native SMBIOS)",
                        "🧪 [LEVEL-C] Experimental Spoof T2 (MacBookPro16,1)",
                        "🧪 [LEVEL-D] All-In-One Tahoe (Wi-Fi + Audio + GPU + T1)"
                    ],
                    "value": "💬 Ask Each Time",
                    "variable": "",
                    "description": [
                        "Change the OpenCore build Config that will be used",
                        "NOTE: setting this to anything other then",
                        "\"Ask Each Time\" will remove the prompt for a config."
                    ]
                },
                "Populate OpenCore Build Override": {
                    "type": "populate",
                    "function": self._populate_oc_build_override,
                    "args": wx.Frame,
                    },
                "wrap_around 1": {
                    "type": "wrap_around",
                },
                "Export constants": {
                    "type": "button",
                    "function": self.on_export_constants,
                    "description": [
                        "Export constants.py values to a txt file.",
                    ],
                },
            },
        }

        return settings





    def _populate_app_stats(self, panel: wx.Frame) -> None:
        title: wx.StaticText = None
        for child in panel.GetChildren():
            if child.GetLabel() == "Statistics":
                title = child
                break

        lines = f"""Application Information:
    Application Version: {self.constants.patcher_version}
    PatcherSupportPkg Version: {self.constants.patcher_support_pkg_version}
    Application Path: {self.constants.launcher_binary}
    Application Mount: {self.constants.payload_path}

Commit Information:
    Branch: {self.constants.commit_info[0]}
    Date: {self.constants.commit_info[1]}
    URL: {self.constants.commit_info[2] if self.constants.commit_info[2] != "" else "N/A"}

Booted Information:
    Booted OS: XNU {self.constants.detected_os} ({self.constants.detected_os_version})
    Booted Patcher Version: {self.constants.computer.oclp_version}
    Booted OpenCore Version: {self.constants.computer.opencore_version}
    Booted OpenCore Disk: {self.constants.booted_oc_disk}

Hardware Information:
    {pprint.pformat(self.constants.computer, indent=4)}
"""
        # TextCtrl: properties
        self.app_stats = wx.TextCtrl(panel, value=lines, pos=(-1, title.GetPosition()[1] + 30), size=(600, 525), style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2 | wx.BORDER_NONE | wx.HSCROLL | wx.VSCROLL | wx.TE_DONTWRAP) #TODO: Fix this to show a scrollbar!!! It has to be in the textCtrl, which is the tricky part
        self.app_stats.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        self.app_stats.SetScrollbar(wx.HORIZONTAL, 0, 600, 1200)

    def _populate_oc_build_override(self, panel: wx.Panel) -> None:
        oc_build_box: wx.Choice = None
        for child in panel.GetChildren():
            if isinstance(child, wx.Choice):
                oc_build_box = child
                break
    
        oc_build_box.Bind(wx.EVT_CHOICE, self.oc_build_selection)
        if self.constants.build_profile == "standard":
            oc_build_box.SetStringSelection("🟢 Standard / Safe Build")
        elif (self.constants.build_profile is None) or (self.constants.build_profile == ""):
            oc_build_box.SetStringSelection("💬 Ask Each Time")
        elif self.constants.build_profile == "test_b":
            oc_build_box.SetStringSelection("🧪 [LEVEL-B] Experimental GPU")
        elif self.constants.build_profile == "test_c":
             oc_build_box.SetStringSelection("🧪 [LEVEL-C] Experimental Tahoe (Native SMBIOS)")
        elif self.constants.build_profile == "test_c_spoofed":
            oc_build_box.SetStringsSelection("🧪 [LEVEL-C] Experimental Spoof T2 (MacBookPro16,1)")
        elif self.constants.build_profile == "test_d":
            oc_build_box.SetStringSelection("🧪 [LEVEL-D] All-In-One Tahoe (Wi-Fi + Audio + GPU + T1)")
    
    def oc_build_selection(self, event: wx.Event) -> None:
        value = event.GetEventObject().GetStringSelection()
        if value == "🟢 Standard / Safe Build":
            logging.info("Updating OC build: Standard")
            self.constants.build_profile = "standard"
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "standard")
            return
        elif value == "💬 Ask Each Time":
            logging.info("Updating OC build: None")
            self.constants.build_profile = ""
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "")
            return
        elif value == "🧪 [LEVEL-B] Experimental GPU":
            logging.info("Updating OC build: Level-B")
            self.constants.build_profile = "test_b"
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "test_b")
            return
        elif value == "🧪 [LEVEL-C] Experimental Tahoe (Native SMBIOS)":
            logging.info("Updating OC build: Level-C")
            self.constants.build_profile = "test_c"
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "test_c")
            return
        elif value == "🧪 [LEVEL-C] Experimental Spoof T2 (MacBookPro16,1)":
            logging.info("Updating OC build: Level-C (Spoofed)")
            self.constants.build_profile = "test_c_spoofed"
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "test_c_spoofed")
            return
        elif value == "🧪 [LEVEL-D] All-In-One Tahoe (Wi-Fi + Audio + GPU + T1)":
            logging.info("Updating OC build: Level-D")
            self.constants.build_profile = "test_d"
            global_settings.GlobalEnviromentSettings().write_property("GUI:oc_build", "test_d")
            return
        

    
    def on_checkbox(self, event: wx.Event, warning_pop: str = "", override_function: bool = False) -> None:
        """
        """
        label = event.GetEventObject().GetLabel()
        value = event.GetEventObject().GetValue()
        if warning_pop != "" and value is True:
            warning = wx.MessageDialog(self.frame_modal, warning_pop, f"Warning: {label}", wx.YES_NO | wx.ICON_WARNING | wx.NO_DEFAULT)
            if warning.ShowModal() == wx.ID_NO:
                event.GetEventObject().SetValue(not event.GetEventObject().GetValue())
                return
            if label == "Allow native models":
                if self.constants.computer.real_model in smbios_data.smbios_dictionary:
                    if self.constants.detected_os > smbios_data.smbios_dictionary[self.constants.computer.real_model]["Max OS Supported"]:
                        chassis_type = "aluminum"
                        if self.constants.computer.real_model in ["MacBook5,2", "MacBook6,1", "MacBook7,1"]:
                            chassis_type = "plastic"
                        dlg = wx.MessageDialog(self.frame_modal, f"This model, {self.constants.computer.real_model}, does not natively support macOS {os_data.os_conversion.kernel_to_os(self.constants.detected_os)}, {os_data.os_conversion.convert_kernel_to_marketing_name(self.constants.detected_os)}. The last native OS was macOS {os_data.os_conversion.kernel_to_os(smbios_data.smbios_dictionary[self.constants.computer.real_model]['Max OS Supported'])}, {os_data.os_conversion.convert_kernel_to_marketing_name(smbios_data.smbios_dictionary[self.constants.computer.real_model]['Max OS Supported'])}\n\nToggling this option will break booting on this OS. Are you absolutely certain this is desired?\n\nYou may end up with a nice {chassis_type} brick 🧱", "Are you certain?", wx.YES_NO | wx.ICON_WARNING | wx.NO_DEFAULT)
                        if dlg.ShowModal() == wx.ID_NO:
                            event.GetEventObject().SetValue(not event.GetEventObject().GetValue())
                            return
        if override_function is True:
            self.settings[self._find_parent_for_key(label)][label]["override_function"](self.settings[self._find_parent_for_key(label)][label]["variable"], value, self.settings[self._find_parent_for_key(label)][label]["constants_variable"] if "constants_variable" in self.settings[self._find_parent_for_key(label)][label] else None)
            return

        self._update_setting(self.settings[self._find_parent_for_key(label)][label]["variable"], value)
        if label == "Allow native models":
            if gui_support.CheckProperties(self.constants).host_can_build() is True:
                self.constants.allow_building = True
            else:
                self.constants.allow_building = False


    def on_spinctrl(self, event: wx.Event, label: str) -> None:
        """
        """
        value = event.GetEventObject().GetValue()
        self._update_setting(self.settings[self._find_parent_for_key(label)][label]["variable"], value)

    def _find_parent_for_key(self, key: str) -> str:
        for parent in self.settings:
            if key in self.settings[parent]:
                return parent


    def on_choice(self, event: wx.Event, label: str) -> None:
        """
        """
        value = event.GetString()
        self._update_setting(self.settings[self._find_parent_for_key(label)][label]["variable"], value)

    def on_return(self, event):
        self.frame_modal.Destroy()

    def _update_global_settings(self, variable, value, global_setting = None):
        logging.info(f"Updating Global Setting: {variable} = {value}")
        tmp_value = value
        if tmp_value is None:
            tmp_value = "PYTHON_NONE_VALUE"
        global_settings.GlobalEnviromentSettings().write_property(variable, tmp_value)
        if global_setting is not None:
            self._update_setting(global_setting, value)


    def on_export_constants(self, event: wx.Event) -> None:
        # Throw pop up to get save location
        with wx.FileDialog(self.parent, "Save Constants File", wildcard="JSON files (*.txt)|*.txt", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, defaultFile=f"constants-{self.constants.patcher_version}.txt") as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            # Save the current contents in the file
            pathname = fileDialog.GetPath()
            logging.info(f"Saving constants to {pathname}")
            with open(pathname, 'w') as file:
                file.write(pprint.pformat(vars(self.constants), indent=4))


    def on_test_exception(self, event: wx.Event) -> None:
        raise Exception("Test Exception")

    def _update_setting(self, variable, value):
        logging.info(f"Updating Local Setting: {variable} = {value}")
        setattr(self.constants, variable, value)
        tmp_value = value
        if tmp_value is None:
            tmp_value = "PYTHON_NONE_VALUE"
        global_settings.GlobalEnviromentSettings().write_property(f"GUI:{variable}", tmp_value)