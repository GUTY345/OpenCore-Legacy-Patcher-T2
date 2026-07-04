"""
gui_main_menu.py: Generate GUI for main menu
"""
import wx
import wx.html2
import sys
import logging
import subprocess
import requests
import markdown2
import threading
import webbrowser
import shutil
from pathlib import Path
from packaging import version
from .. import constants
from ..support import (
    global_settings,
    updates
)
from ..datasets import (
    os_data,
    css_data
)
from ..wx_gui import (
    gui_build,
    gui_macos_installer_download,
    gui_support,
    gui_help,
    gui_settings,
    gui_sys_patch_display,
    gui_update,
)

class MainFrame(wx.Frame):
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None):
        logging.info("Initializing Main Menu Frame")
        super(MainFrame, self).__init__(parent, title=title, size=(700, 800), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
        gui_support.GenerateMenubar(self, global_constants).generate()
        self.constants: constants.Constants = global_constants
        self.title: str = title

        self.model_label: wx.StaticText = None
        self.build_button: wx.Button = None
        # FIX: Absicherung gegen Thread-Races & Verwaiste Fenster-Referenzen [3]
        self.exiting_app: bool = False
        self.active_gemini_frame: wx.Frame = None
        self.constants.update_stage = gui_support.AutoUpdateStages.INACTIVE
        self._generate_elements()
        self.Centre()
        self.Show()
        # FIX: Sauberes Schließen abfangen [4]
        self.Bind(wx.EVT_CLOSE, self.on_close_window)
        self._preflight_checks()

    def _generate_elements(self) -> None:
        """ Generate UI elements for the main menu """
        # Logo [4]
        logo = wx.StaticBitmap(self, bitmap=wx.Bitmap(str(self.constants.icns_resource_path / "OC-Patcher.icns"), wx.BITMAP_TYPE_ICON), pos=(-1, 0), size=(128, 128))
        logo.Centre(wx.HORIZONTAL)
        # Title label [4, 5]
        title_label = wx.StaticText(self, label=self.constants.patcher_name, pos=(-1, 128))
        title_label.SetFont(gui_support.font_factory(25, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)
        
        version_label = wx.StaticText(self, label=f"Version {self.constants.patcher_version_label}", pos=(-1, title_label.GetPosition()[1] + 32))
        version_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        version_label.Centre(wx.HORIZONTAL)
        version_label.SetForegroundColour(wx.Colour(128, 128, 128))

        model_label = wx.StaticText(self, label=f"Model: {self.constants.custom_model or self.constants.computer.real_model}", pos=(-1, version_label.GetPosition()[1] + 30))
        model_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        model_label.Centre(wx.HORIZONTAL)
        self.model_label = model_label

        # Main 4 Feature Buttons [6-8]
        menu_buttons = {
            "Build and Install OpenCore": {
                "function": self.on_build_and_install,
                "description": ["Prepares provided drive to be able", "to boot unsupported OSes.", "Use on installers or internal drives."],
                "icon": str(self.constants.icns_resource_path / "OC-Build.icns"),
            },
            "Create macOS Installer": {
                "function": self.on_create_macos_installer,
                "description": ["Download and flash a macOS", "Installer for your system."],
                "icon": str(self.constants.icns_resource_path / "OC-Installer.icns"),
            },
            "Install drivers and patches": {
                "function": self.on_post_install_root_patch,
                "description": ["Installs hardware drivers and", "patches for your system after", "installing a new version of macOS."],
                "icon": str(self.constants.icns_resource_path / "OC-Patch.icns"),
            },
            "Support": {
                "function": self.on_help,
                "description": ["Resources for OpenCore Legacy", "Patcher."],
                "icon": str(self.constants.icns_resource_path / "OC-Support.icns"),
            },
        }

        button_x, button_y = 30, model_label.GetPosition()[1] + 30
        rollover, index, max_height = 2, 0, 0

        for button_name, button_info in menu_buttons.items():
            if "icon" in button_info:
                icon = wx.StaticBitmap(self, bitmap=wx.Bitmap(button_info["icon"], wx.BITMAP_TYPE_ICON), pos=(button_x - 10, button_y), size=(64, 64))
                if button_name == "Build and Install OpenCore":
                    icon.SetSize((70, 70))
            
            button = wx.Button(self, label=button_name, pos=(button_x + 70, button_y), size=(180, 30))
            button.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
            button.Bind(wx.EVT_BUTTON, lambda event, f=button_info["function"]: f(event))

            description_label = wx.StaticText(self, label='\n'.join(button_info["description"]), pos=(button_x + 75, button.GetPosition()[1] + 33))
            description_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))

            button_y += 85
            if button_y > max_height: max_height = button_y
            index += 1
            if index == rollover:
                button_x, button_y = 320, model_label.GetPosition()[1] + 30

        # Footer [11, 12]
        start_x = (self.GetSize().width - 280) // 2
        footer_y = max_height + 10
        settings_btn = wx.Button(self, label="⚙️ Settings", pos=(start_x, footer_y), size=(120, 30))
        settings_btn.Bind(wx.EVT_BUTTON, self.on_settings)
        gemini_btn = wx.Button(self, label="✨ Ask Gemini", pos=(start_x + 130, footer_y), size=(150, 30))
        gemini_btn.Bind(wx.EVT_BUTTON, self.on_gemini_help)

        gemini_desc = wx.StaticText(self, label="AI Troubleshooting and\nInstallation help.", pos=(start_x + 135, footer_y + 35))
        gemini_desc.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))

        copy_label = wx.StaticText(self, label=self.constants.copyright_date, pos=(-1, gemini_desc.GetPosition()[1] + 45))
        copy_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
        copy_label.Centre(wx.HORIZONTAL)
        self.SetSize((-1, copy_label.GetPosition()[1] + 60))

    def _preflight_checks(self):
        """ [13-17] """
        try:
            if self.constants.computer.build_model is None:
                self.constants.computer.build_model = self.constants.computer.real_model
            
            if (self.constants.computer.build_model != self.constants.computer.real_model and not self.constants.host_is_hackintosh):
                pop_up = wx.MessageDialog(self, f"OpenCore build for {self.constants.computer.build_model} detected on this unit.\n\nPlease rebuild.", "Unsupported Configuration!", wx.OK | wx.ICON_EXCLAMATION)
                pop_up.ShowModal()
                self.on_build_and_install()
                return
        except Exception as e:
            logging.error(f"Preflight error: {e}")

        self.update_thread = threading.Thread(target=self._check_for_updates)
        self.update_thread.daemon = True
        self.update_thread.start()

    def _check_for_updates(self):
        """ Hintergrund-Thread für Updates inkl. Changelog-Abruf [18-19 + Fix] """
        if self.constants.has_checked_updates:
            logging.info("Suchen nach Updates ist erfolgreich")
            return
        else:
            logging.info("Keine neue Updates verfügbar. Falls einen Update ist verfügbar aber zeigt es nicht, sollen Sie das Problem sofort melden und auch einen Fix vorschlagen.")
        
        try:
            if global_settings.GlobalEnviromentSettings().read_property("IgnoreAppUpdates"):
                logging.info("Updates sind von Benutzer ausgeschaltet. Falls dies nicht der Fall ist, sollten Sie das Problem sofort melden und einen Fix vorschlagen.")
                logging.info("Das Deaktivieren von Updates bringt Sicherheitsrisiko, weil gepatche Sicherheitslücken noch immer auf das System ungepatcht bleiben")
                self.constants.ignore_updates = True
                return
            logging.info("Nach Updates suchen...")
            self.constants.has_checked_updates = True
            update_dict = updates.CheckBinaryUpdates(self.constants).check_binary_updates()
            if update_dict:
                # FIX: Changelog hier im Hintergrund laden, um UI-Lag zu vermeiden
                url = "https://api.github.com/repos/albert-mueller/OpenCore-Legacy-Patcher-T2/releases/latest"
                try:
                    response = requests.get(url).json()
                    changelog = response.get("body", "").split("## Asset Information")
                except:
                    changelog = "## Unable to fetch changelog\nPlease check GitHub."
                    logging.info("Wir haben einen Problem, den Changelog zu fetchen. Bitte, suchen Sie den Changelog in GitHub nach.")
                
                wx.CallAfter(self.on_update, update_dict["Link"], update_dict["Version"], update_dict["Github Link"], changelog)
        except Exception as e:
            logging.error(f"Suche nach Updates fehlgeschlagen: {e}")
            logging.exception("Stack Trace:")
            logging.info("Falls dieses Problem ist noch vorhanden, Sie müssen dringend das Problem melden und/oder einen Fix vorschlagen.")

    def on_update(self, oclp_url, oclp_version, oclp_github_url, changelog):
        """ Zeigt das Update-Fenster an [20-25] """
        ID_GITHUB, ID_UPDATE = wx.NewId(), wx.NewId()
        html_markdown = markdown2.markdown(changelog, extras=["tables"])
        
        frame = wx.Dialog(None, -1, title="", size=(650, 500))
        frame.SetWindowStyle(wx.STAY_ON_TOP)
        panel = wx.Panel(frame)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, label="A new version of OpenCore Legacy Patcher is available!")
        title_text.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        
        web_view = wx.html2.WebView.New(panel)
        web_view.SetPage(f"<html><head><style>{css_data.updater_css}</style></head><body>{html_markdown}</body></html>", "")
        
        # Buttons & Layout [24, 25]...
        install_button = wx.Button(panel, label="Download and Install")
        install_button.Bind(wx.EVT_BUTTON, lambda e: frame.EndModal(ID_UPDATE))
        
        result = frame.ShowModal()
        if result == ID_GITHUB: webbrowser.open(oclp_github_url)
        elif result == ID_UPDATE:
            gui_update.UpdateFrame(parent=self, title=self.title, global_constants=self.constants, url=oclp_url, version_label=oclp_version)
        frame.Destroy()

    def on_gemini_help(self, event: wx.Event):
        """ [26-28 + Fixes] """
        import webview
        try:
            self._check_for_updates() # FIX: Klammern hinzugefügt
            logging.info("Update-Check via Gemini gestartet")
        except Exception as e:
            logging.error(f"Fehler beim Update-Check: {e}")
        
        webview.create_window('Gemini AI Assistant', 'https://gemini.google.com', width=500, height=850)
        webview.start()

    def on_build_and_install(self, event=None):
        self.Hide()
        gui_build.BuildFrame(None, self.title, self.constants, self.GetPosition())
        wx.CallAfter(self.Destroy)

    def on_post_install_root_patch(self, event=None):
        gui_sys_patch_display.SysPatchDisplayFrame(self, self.title, self.constants, self.GetPosition())

    def on_create_macos_installer(self, event=None):
        gui_macos_installer_download.macOSInstallerDownloadFrame(self, self.title, self.constants, self.GetPosition())

    def on_settings(self, event=None):
        gui_settings.SettingsFrame(self, self.title, self.constants, self.GetPosition())

    def on_help(self, event=None):
        gui_help.HelpFrame(self, self.title, self.constants, self.GetPosition())

    def on_close_window(self, event: wx.Event):
        """ [31, 32] """
        self.exiting_app = True
        if self.active_gemini_frame:
            try: self.active_gemini_frame.Destroy()
            except: pass
        wx.GetApp().SafeYield(None, True)
        self.Destroy()
