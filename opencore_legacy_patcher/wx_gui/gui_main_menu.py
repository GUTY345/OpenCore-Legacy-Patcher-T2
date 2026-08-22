"""
gui_main_menu.py: Generate GUI for main menu
"""

import wx
import wx.html2

import sys
import logging
import requests
import markdown2
import threading
import webbrowser
import applescript
from packaging import version

from .. import constants

from ..support import (
    updates,
    subprocess_wrapper
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
    gui_macos_configeration,
    gui_model_change,
    gui_oc_settings,
    gui_update,
)

class MainFrame(wx.Frame):
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None):
        logging.info("Initializing Main Menu Frame")
        super(MainFrame, self).__init__(parent, title=title, size=(600, 400), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
        gui_support.GenerateMenubar(self, global_constants).generate()

        self.constants: constants.Constants = global_constants
        self.title: str = title

        self.model_label: wx.StaticText = None
        self.build_button: wx.Button = None
        
        # FIX: Absicherung gegen Thread-Races & Verwaiste Fenster-Referenzen
        self.exiting_app: bool = False  
        self.active_gemini_frame: wx.Frame = None

        self.constants.update_stage = gui_support.AutoUpdateStages.INACTIVE

        self._generate_elements()

        self.Centre()
        self.Show()

        self._preflight_checks()

    def _generate_elements(self) -> None:
        """
        Generate UI elements for the main menu
        """
        # Logo
        logo = wx.StaticBitmap(self, bitmap=wx.Bitmap(str(self.constants.icns_resource_path / "OC-Patcher.icns"), wx.BITMAP_TYPE_ICON), pos=(-1, 0), size=(128, 128))
        logo.Centre(wx.HORIZONTAL)

        # Title label
        title_label = wx.StaticText(self, label=self.constants.patcher_name, pos=(-1, 128))
        title_label.SetFont(gui_support.font_factory(25, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)

        version_label = wx.StaticText(self, label=f"Version {self.constants.patcher_version_label}", pos=(-1, title_label.GetPosition()[1] + 32))
        version_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        version_label.Centre(wx.HORIZONTAL)
        version_label.SetForegroundColour(wx.Colour(128, 128, 128))
        try:
            if self.constants.Developer_Mode:
                dev_label = wx.StaticText(self, label="Developer Mode is ON", pos=(-1, version_label.GetPosition()[1] + 20))
                dev_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
                dev_label.Centre(wx.HORIZONTAL)
                dev_label.SetForegroundColour(wx.Colour(100, 196, 102))
    
                model_Button = wx.Button(self, label=f"Model: {self.constants.custom_model or self.constants.computer.real_model}", pos=(-1, version_label.GetPosition()[1] + 40))
            else:
                model_Button = wx.Button(self, label=f"Model: {self.constants.custom_model or self.constants.computer.real_model}", pos=(-1, version_label.GetPosition()[1] + 30))
        except Exception as e:
            logging.error("We couldn't verify whether Developer Mode is on or off due to a critical bug.")
            logging.info("Please, report this bug.")
            logging.exception("The error is the following:")
            logging.info("Since we couldn't verify this, we'll assume Developer Mode is disabled.")
        model_Button.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        model_Button.Centre(wx.HORIZONTAL)
        model_Button.SetToolTip("Edit the Target Model OpenCore will build for")
        model_Button.Bind(wx.EVT_BUTTON, lambda event, function=self.on_edit_model: function(event))
        self.model_button = model_Button

        # Main 5 Feature Buttons
        menu_buttons = {
            "OpenCore": {
                "function": self.on_oc_settings,
                "description": [
                    "Prepares provided drive to be able",
                    "to boot unsupported OSes.",
                    "Use on installers or internal drives."
                ],
                "icon": str(self.constants.icns_resource_path / "OC-Build.icns"),
            },
            "Create macOS Installer": {
                "function": self.on_create_macos_installer,
                "description": [
                    "Download and flash a macOS",
                    "Installer for your system.",
                ],
                "icon": str(self.constants.icns_resource_path / "OC-Installer.icns"),
            },
            "⚙️ Settings": {
                "function": self.on_settings,
                "description": [
                ],
            },
            "macOS Configeration": {
                "function": self.on_macos_config,
                "description": [
                    "Settings,",
                    "drivers and patches for",
                    "your system.",
                ],
                "icon": str(self.constants.patch_icon_path),
            },

            "Support": {
                "function": self.on_help,
                "description": [
                    "Resources for OpenCore Legacy",
                    "Patcher T2, including Ask Gemini.",
                ],
                "icon": str(self.constants.icns_resource_path / "OC-Support.icns"),
            },
        }

        button_x = 30
        button_y = model_Button.GetPosition()[1] + 30
        rollover = len(menu_buttons) / 2
        if rollover % 1 != 0:
            rollover = int(rollover) + 1
        index = 0
        max_height = 0
        for button_name, button_function in menu_buttons.items():
            # place icon
            if "icon" in button_function:
                icon = wx.StaticBitmap(self, bitmap=wx.Bitmap(button_function["icon"], wx.BITMAP_TYPE_ICON), pos=(button_x - 10, button_y), size=(64, 64))
                if button_name == "MacOS Configeration":
                    icon.SetPosition((-1, button_y + 7))
                if button_name == "Create macOS Installer":
                    icon.SetPosition((button_x - 5, button_y + 3))
                if button_name == "Support":
                    # icon_mac.SetSize((80, 80))
                    icon.SetPosition((button_x - 7, button_y + 3))
                if button_name == "OpenCore":
                    icon.SetSize((70, 70))
            if button_name == "⚙️ Settings":
                button_y += 5

            button = wx.Button(self, label=button_name, pos=(button_x + 70, button_y), size=(180, 30))
            button.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
            button.Bind(wx.EVT_BUTTON, lambda event, function=button_function["function"]: function(event))
            button_y += 30

            # # Text: Description
            description_label = wx.StaticText(self, label='\n'.join(button_function["description"]), pos=(button_x + 75, button.GetPosition()[1] + button.GetSize()[1] + 3))
            description_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
            # button_y += 15

            for i, line in enumerate(button_function["description"]):
                if line == "":
                    continue
                if i == 0:
                    button_y += 11
                else:
                    button_y += 13

            button_y += 25


            if button_name == "MacOS Configeration":
                if self.constants.detected_os <= os_data.os_data.big_sur:
                    button.Disable()
            elif button_name == "⚙️ Settings":
                button.SetSize((100, -1))
                button.Centre(wx.HORIZONTAL)
                description_label.Centre(wx.HORIZONTAL)

            index += 1
            if index == rollover:
                max_height = button_y
                button_x = 320
                button_y = model_Button.GetPosition()[1] + 30


        # Text: Copyright
        copy_label = wx.StaticText(self, label=self.constants.copyright_date, pos=(-1, max_height - 15))
        copy_label.SetFont(gui_support.font_factory(10, wx.FONTWEIGHT_NORMAL))
        copy_label.Centre(wx.HORIZONTAL)

        # Set window size
        self.SetSize((-1, copy_label.GetPosition()[1] + 50))


    def _preflight_checks(self):
        try:
            if self.constants.computer.build_model is None:
                logging.info("No build model detected. Defaulting to current host hardware.")
                self.constants.computer.build_model = self.constants.computer.real_model
            
            real_model = str(self.constants.computer.real_model).strip()
            build_model = str(self.constants.computer.build_model).strip() if self.constants.computer.build_model else None
            
            print(f"DEBUG: Real: '{real_model}' | Build: '{build_model}'")

            if (
                build_model is not None and
                build_model != real_model and
                self.constants.host_is_hackintosh is False
            ):
                pop_up = wx.MessageDialog(
                    self,
                    f"We found you are currently booting OpenCore built for a different unit: {build_model}\n\nPlease Build and Install a new OpenCore config.",
                    "Unsupported Configuration Detected!",
                    style=wx.OK | wx.ICON_EXCLAMATION
                )
                pop_up.ShowModal()
                self.on_build_and_install()
                return

        except Exception as e:
            logging.error(f"DEBUG: Preflight error: {e}")
            logging.exception("Stack Trace:")
            logging.info("Please report this bug.")

        self.update_thread = threading.Thread(target=self._check_for_updates)
        self.update_thread.daemon = True  
        self.update_thread.start()

        if "--update_installed" in sys.argv and self.constants.has_checked_updates is False and gui_support.CheckProperties(self.constants).host_can_build():
            self.constants.has_checked_updates = True
            pop_up = wx.MessageDialog(
                self,
                f"{self.constants.patcher_name} has been updated to the latest version: {self.constants.patcher_version_label}\n\nWould you like to update OpenCore and your root volume patches?",
                "Update successful!",
                style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION
            )
            pop_up.ShowModal()

            if pop_up.GetReturnCode() != wx.ID_YES:
                logging.info("Skipping OpenCore and root volume patch update...")
                return
            # behebt 2 Sicherheitslücken: eine erlaubt Angreifern, unkonditionell OpenCore-Aktualisierungen durchzuführen ohne Erlaubnis von Benutzer, auch wenn der Benutzer "Nein/No" geklickt hat. Die andere Sicherheitslücke erlaubt Angreifern beim fehlerhafte Aktualisierung von OpenCore, der App zum Absturz zu bringen.
            else:
                try:
                    logging.info("Updating OpenCore and root volume patches...")
                    self.constants.update_stage = gui_support.AutoUpdateStages.CHECKING
                    self.Hide()
                    pos = self.GetPosition()
                    gui_build.BuildFrame(
                        parent=None,
                        title=self.title,
                        global_constants=self.constants,
                        screen_location=pos,
                        install=True
                    )
                    wx.CallAfter(self.Destroy)
                except Exception as e:
                    logging.error("Updating OpenCore and root patches has failed due to the following error:")
                    logging.exception("Stack Trace:")
                    logging.info("Try rebuilding OpenCore again and ensure the root patches haven't been broken.")
                    return

    def _request_admin_password_for_helper_repair(self) -> str:
        """
        Prompt for the local administrator password via a plain dialog, so it
        can be handed to sudo ourselves for repairing the Privileged Helper
        Tool's permissions.

        Deliberately not "do shell script ... with administrator privileges"
        for the same reason as PatcherSupportPkgMount._request_admin_password:
        that mechanism runs elevated via a separate authorization session
        (/usr/libexec/security_authtrampoline) detached from the current
        login/Aqua session. A plain "display dialog" only needs a
        WindowServer session to render, so we use it purely to collect the
        password.
        """
        try:
            return applescript.AppleScript(
                f'set theResult to display dialog "OpenCore Legacy Patcher needs administrator access to repair the Privileged Helper Tool\'s permissions." default answer "" with hidden answer with title "OpenCore Legacy Patcher" with icon file "{str(self.constants.app_icon_path).replace("/", ":")[1:]}"\nreturn the text returned of theResult'
            ).run()
        except Exception:
            return ""

    def _ensure_privileged_helper_permissions(self) -> None:
        """
        Ensure the Privileged Helper Tool still has its expected 4755
        (setuid root, rwxr-xr-x) permissions before we reach out to check
        for updates, repairing them first if needed.

        Only prompts for a password when a repair is actually needed, so
        this doesn't nag the user with a sudo prompt on every launch.
        """
        if not subprocess_wrapper.privileged_helper_needs_setuid_repair():
            logging.info("Privileged Helper Tool permissions are already correct, no repair needed")
            return

        logging.info("Privileged Helper Tool permissions need repair, requesting administrator password")
        admin_password = self._request_admin_password_for_helper_repair()
        if not admin_password:
            logging.info("Skipped Privileged Helper Tool permission repair (no password provided)")
            return

        subprocess_wrapper.repair_privileged_helper_permissions(admin_password)

    def _check_for_updates(self):
        if self.constants.has_checked_updates is True:
            logging.info("We have already checked for updates.")
            return
        # behebt eine Sicherheitslücke, die erlaubt Angreifern, trotz es schon nach Updates gesucht wurden, wieder nach Updates zu suchen, um den Mac und die API fürs Updates zu überlasten.
        # behebt auch eine Sicherheitslücke, die erlaubt Angreifern, Updates zu deaktivieren, um aus bereits bekannten Sicherheitslücken auszunutzen.
        else:
            logging.info("Checking for updates")
            self.constants.has_checked_updates = True

            self._ensure_privileged_helper_permissions()

            update_dict = updates.CheckBinaryUpdates(self.constants).check_binary_updates()
            if not update_dict:
                return
        
            remote_version_str = update_dict["Version"]
            local_version_str = self.constants.patcher_version
        
            try:
                remote_v = version.parse(str(remote_version_str))
                local_v = version.parse(local_version_str)
        
                if remote_v <= local_v:
                    logging.info(f"{self.constants.patcher_name} is up to date. (Local: {local_v} >= Remote: {remote_v})")
                    return
        
            except version.InvalidVersion:
                logging.error("Your version is invalid")
                if remote_version_str == local_version_str:
                    return
            # behebt eine Sicherheitslücke, indem beim unerwartetes Fehler das App einfach abstürzt. Angreifern können davon ausnutzen, um invalider Syntax zu schreiben, um beliebiges Code aus[...]
            except Exception as e:
                logging.error("We face some issues checking for updates. The error is the following:")
                logging.exception("Stack Trace:")
                logging.info("Check for available updates in the OpenCore Legacy Patcher T2 repository. At the moment, the builtin updater is not working as intended.")
                return
        
            if getattr(self, 'exiting_app', False) or gui_support.is_app_exiting():
                return
    
            logging.info(f"Newer version detected: {remote_version_str}")
            
            url = "https://api.github.com/repos/albert-mueller/OpenCore-Legacy-Patcher-T2/releases/latest"
            changelog = """## Unable to fetch changelog\n\nPlease check the Github page for more information."""
            try:
                response = requests.get(url, headers={"User-Agent": "OpenCore-Legacy-Patcher-T2"}, timeout=10).json()
                if "body" in response:
                    changelog = response["body"].split("## Asset Information")[0]
            except Exception as e:
                logging.error(f"Failed to fetch changelog text: {e}")
                logging.exception("Stack Trace:")
    
            if not getattr(self, 'exiting_app', False) and not gui_support.is_app_exiting():
                wx.CallAfter(self.on_update, update_dict["Link"], remote_version_str, update_dict["Github Link"], changelog)
        
    def on_update(self, oclp_url: str, oclp_version: str, oclp_github_url: str, changelog_text: str):
        if not self or gui_support.is_app_exiting():
            return

        ID_GITHUB = wx.NewIdRef() if hasattr(wx, "NewIdRef") else wx.NewId()
        ID_UPDATE = wx.NewIdRef() if hasattr(wx, "NewIdRef") else wx.NewId()

        html_markdown = markdown2.markdown(changelog_text, extras=["tables"])
        html_css = css_data.updater_css
        
        # Parent auf self gesetzt zur sauberen Speicherhierarchie
        frame = wx.Dialog(self, -1, title="", size=(650, 500))
        frame.SetMinSize((650, 500))
        frame.SetWindowStyle(wx.STAY_ON_TOP)
        panel = wx.Panel(frame)
        
        self.title_text = wx.StaticText(panel, label=f"A new version of {self.constants.patcher_name} is available!")
        self.description = wx.StaticText(panel, label=f"{self.constants.patcher_name} {oclp_version} is now available - You have {self.constants.patcher_version_label}. Would you like to update?")
        self.title_text.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        self.description.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        # Ohne Wrap() ragt der Text bei langen Versions-/Produktnamen über die feste Dialogbreite hinaus
        # und wird dadurch abgeschnitten (z.B. "Would you like to update?" -> "Would you like to").
        self.description.Wrap(600)
        
        self.web_view = wx.html2.WebView.New(panel, style=wx.BORDER_SUNKEN)
        html_code = f'''
<html>
    <head>
        <style>
            {html_css}
        </style>
    </head>
    <body class="markdown-body">
        {html_markdown.replace("<a href=", "<a target='_blank' href=")}
    </body>
</html>
'''
        self.web_view.SetPage(html_code, "")
        self.web_view.Bind(wx.html2.EVT_WEBVIEW_NEWWINDOW, self._onWebviewNav)
        self.web_view.EnableContextMenu(False)
        
        self.close_button = wx.Button(panel, label="Update Later")
        self.close_button.Bind(wx.EVT_BUTTON, lambda event: frame.EndModal(wx.ID_CANCEL))
        self.view_button = wx.Button(panel, ID_GITHUB, label="View on GitHub")
        self.view_button.Bind(wx.EVT_BUTTON, lambda event: frame.EndModal(ID_GITHUB))
        self.install_button = wx.Button(panel, label="Update Now")
        self.install_button.Bind(wx.EVT_BUTTON, lambda event: frame.EndModal(ID_UPDATE))
        self.install_button.SetDefault()

        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonsizer.Add(self.close_button, 0, wx.ALIGN_CENTRE | wx.RIGHT, 5)
        buttonsizer.Add(self.view_button, 0, wx.ALIGN_CENTRE | wx.LEFT|wx.RIGHT, 5)
        buttonsizer.Add(self.install_button, 0, wx.ALIGN_CENTRE | wx.LEFT, 5)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.title_text, 0, wx.ALIGN_CENTRE | wx.TOP, 20)
        sizer.Add(self.description, 0, wx.ALIGN_CENTRE | wx.BOTTOM, 20)
        sizer.Add(self.web_view, 1, wx.EXPAND | wx.LEFT|wx.RIGHT, 10)
        sizer.Add(buttonsizer, 0, wx.ALIGN_RIGHT | wx.ALL, 20)
        panel.SetSizer(sizer)
        frame.Centre()

        result = frame.ShowModal()

        if result == ID_GITHUB:
            webbrowser.open(oclp_github_url)
        elif result == ID_UPDATE:
            gui_update.UpdateFrame(
                parent=self,
                title=self.title,
                global_constants=self.constants,
                screen_location=self.GetPosition(),
                url=oclp_url,
                version_label=oclp_version
            )

        frame.Destroy()

    def _onWebviewNav(self, event):
        url = event.GetURL()
        webbrowser.open(url)


    def on_edit_model(self, event: wx.Event = None):
        self.Disable()
        gui_model_change.ModelPickerFrame(
        parent=self,
        title=self.title,
        global_constants=self.constants,
        screen_location=self.GetPosition(),
        )
        
    def on_oc_settings(self, event: wx.Event = None):
        self.Hide
        gui_oc_settings.OCSettingsFrame(
            parent=self,
            title=self.title,
            global_constants=self.constants,
            screen_location=self.GetPosition()
        )
        

    def on_build_and_install(self, event: wx.Event = None):
        try:
            self.Hide()
            gui_build.BuildFrame(parent=None, title=self.title, global_constants=self.constants, screen_location=self.GetPosition())
            wx.CallAfter(self.Destroy)
        except Exception as e:
            logging.error(f"We failed to open up Build and Install OpenCore: {e}")
            logging.exception("Stack Trace:")
            return

    def on_post_install_root_patch(self, event: wx.Event = None):    
        try:
            gui_sys_patch_display.SysPatchDisplayFrame(parent=self, title=self.title, global_constants=self.constants, screen_location=self.GetPosition())
        except Exception as e:
            logging.error(f"Failed to open Install drivers and patches: {e}")
            logging.exception("Stack Trace:")
            return

    def on_macos_config(self, event: wx.Event = None):
        try:
            gui_macos_configeration.MacosConfigFrame(
                parent=self,
                title=self.title,
                global_constants=self.constants,
                screen_location=self.GetPosition()
            )
        except Exception as e:
            logging.error(f"We failed to open MacOS Configuration: {e}")
            logging.exception("Stack Trace:")
            return

    def on_create_macos_installer(self, event: wx.Event = None):
        try:
            gui_macos_installer_download.macOSInstallerDownloadFrame(parent=self, title=self.title, global_constants=self.constants, screen_location=self.GetPosition())
        except Exception as e:
            logging.error(f"We failed to open up Download macOS: {e}")
            logging.exception("Stack Trace:")
            return

    def on_settings(self, event: wx.Event = None):
        try:
            gui_settings.SettingsFrame(parent=self, title=self.title, global_constants=self.constants, screen_location=self.GetPosition())
        except Exception as e:
            logging.error(f"We failed to open up Settings: {e}")
            logging.exception("Stack Trace:")
            return

    def on_help(self, event: wx.Event = None):
        try:
            gui_help.HelpFrame(parent=self, title=self.title, global_constants=self.constants, screen_location=self.GetPosition())
        except Exception as e:
            logging.error(f"We failed to open up Help: {e}")
            logging.exception("Stack Trace:")
            return
