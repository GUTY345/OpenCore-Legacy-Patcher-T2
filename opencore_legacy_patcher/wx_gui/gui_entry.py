"""
gui_entry.py: Entry point for the wxPython GUI
"""

import wx
import sys
import logging

from Cocoa import NSApp, NSApplication

from .. import constants
from ..sys_patch.patchsets import HardwarePatchsetDetection

from ..wx_gui import (
    gui_cache_os_update,
    gui_main_menu,
    gui_build,
    gui_install_oc,
    gui_sys_patch_start,
    gui_support,
    gui_update,
)


class SupportedEntryPoints:
    """
    Enum for supported entry points
    """
    MAIN_MENU  = gui_main_menu.MainFrame
    BUILD_OC   = gui_build.BuildFrame
    INSTALL_OC = gui_install_oc.InstallOCFrame
    SYS_PATCH  = gui_sys_patch_start.SysPatchStartFrame
    UPDATE_APP = gui_update.UpdateFrame
    OS_CACHE   = gui_cache_os_update.OSUpdateFrame


class PatcherApp(wx.App):
    """
    wx.App subclass so we have a reliable, single place to clean up on
    quit -- OnExit() fires on every quit path (Cmd+Q, Dock > Quit, or the
    last window closing), regardless of which frame is currently active.
    A frame-level EVT_CLOSE handler only ever covers the one frame it was
    bound to, which isn't enough since this app constantly destroys one
    top-level frame and creates another as the user navigates.
    """

    def OnExit(self) -> int:
        # Stop any still-running gauge pulse thread before Cocoa tears
        # down the window it's animating -- letting it keep firing
        # wx.CallAfter() into a vanishing frame is what corrupts the
        # autorelease pool on quit.
        gui_support.stop_all_pulses()
        return super().OnExit()


class EntryPoint:

    def __init__(self, global_constants: constants.Constants) -> None:
        self.app: wx.App = None
        self.frame: wx.Frame = None
        self.main_menu_frame: gui_main_menu.MainFrame = None
        self.constants: constants.Constants = global_constants

        self.constants.gui_mode = True


    def _generate_base_data(self) -> None:
        self.app = PatcherApp()
        self.app.SetAppName(self.constants.patcher_name)

        # Reference:
        # - https://discuss.wxpython.org/t/macos-window-opens-in-the-background-and-does-not-receive-focus/36763/10
        NSApplication.sharedApplication()
        NSApp().activateIgnoringOtherApps_(True)


    def start(self, entry: SupportedEntryPoints = gui_main_menu.MainFrame, start_patching: bool = False) -> None:
        """
        Launches entry point for the wxPython GUI
        """
        self._generate_base_data()

        # BEHOBEN: "patches" initialisieren, um UnboundLocalError/NameError im else-Zweig zu verhindern
        patches = None
        is_patching_mode = "--gui_patch" in sys.argv or "--gui_unpatch" in sys.argv or start_patching is True

        if is_patching_mode:
            entry = gui_sys_patch_start.SysPatchStartFrame
            patches = HardwarePatchsetDetection(constants=self.constants).device_properties

        logging.info(f"Entry point set: {entry.__name__}")

        # Normally set by main.py, but transitions from CLI mode may not have this set
        self.constants.gui_mode = True

        self.frame = entry(
            None,
            title=f"{self.constants.patcher_name} {self.constants.patcher_version}",
            global_constants=self.constants,
            screen_location=None,
            **({"patches": patches} if is_patching_mode else {})
        )

        # BEHOBEN: Gefährliches atexit.register entfernt. 
        # Stattdessen nutzen wir das native wxPython Event-Handling für das Schließen des Fensters.
        self.frame.Bind(wx.EVT_CLOSE, self.OnCloseFrame)

        if "--gui_patch" in sys.argv or start_patching is True:
            self.frame.start_root_patching()
        elif "--gui_unpatch" in sys.argv:
            self.frame.revert_root_patching()

        self.app.MainLoop()


    def OnCloseFrame(self, event: wx.Event = None) -> None:
        """
        Closes the wxPython GUI safely using wxWidgets native event lifecycle
        """
        if not self.frame:
            if event:
                event.Skip()
            return

        logging.info("Cleaning up wxPython GUI")

        self.frame.SetTransparent(0)
        wx.Yield()

        self.frame.DestroyChildren()
        self.frame.Destroy()
        
        # Sicherstellen, dass die MainLoop sauber beendet wird
        if self.app:
            self.app.ExitMainLoop()
            
        # Erlaubt dem System, das Event final zu verarbeiten, falls vorhanden
        if event:
            event.Skip()
