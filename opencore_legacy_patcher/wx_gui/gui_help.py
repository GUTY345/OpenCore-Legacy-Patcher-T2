"""
gui_help.py: GUI Help Menu with added Repository Support Resources
"""

import wx
import logging
import webbrowser

from .. import constants
from ..wx_gui import gui_support

logger = logging.getLogger(__name__)


class HelpFrame(wx.Frame):
    """
    Append to main menu through a modal dialog
    """
    def __init__(self, parent: wx.Frame, title: str, global_constants: constants.Constants, screen_location: tuple = None) -> None:
        logger.info("Initializing Help Frame")
        
        # INCREASED BASE SIZE: Changed vertical boundary constraint from 200 to 300 to accommodate more buttons cleanly
        self.dialog = wx.Dialog(parent, title=title, size=(300, 320))

        self.constants: constants.Constants = global_constants
        self.title: str = title

        self._generate_elements(self.dialog)
        self.dialog.ShowWindowModal()

    def _generate_elements(self, frame: wx.Frame = None) -> None:
        """
        Format:
            - Title: Patcher Resources
            - Text:  Following resources are available:
            - Button: Official Guide
            - Button: Community Discord Server
            - Button: Bug Reports / GitHub Issues  <-- Added
            - Button: Community Discussions        <-- Added
            - Button Gemini
            - Button: Return to Main Menu
        """
        frame = self if not frame else frame

        # 1. Main Title Header
        title_label = wx.StaticText(frame, label="Patcher Resources", pos=(-1, 10))
        title_label.SetFont(gui_support.font_factory(19, wx.FONTWEIGHT_BOLD))
        title_label.Centre(wx.HORIZONTAL)

        # 2. Informational Context Label
        text_label = wx.StaticText(frame, label="Following resources are available:", pos=(-1, 40))
        text_label.SetFont(gui_support.font_factory(13, wx.FONTWEIGHT_NORMAL))
        text_label.Centre(wx.HORIZONTAL)

        # Track the starting Y position dynamically below the description text block
        current_y = text_label.GetPosition()[1] + text_label.GetSize()[1] + 15
        button_spacing = 35  # Clean pixel tracking padding gaps between buttons

        # Define external target items using structured tuples instead of a dict mapping loop
        # Pulls from constants.py configuration bindings cleanly
        resource_links = [
            ("View official GitHub repository", getattr(self.constants, "github_official_link", "https://share.google/wPHFvNb9hJ86pGJg0")),
            ("View official GitHub Issues", getattr(self.constants, "github_issues_link", "https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2/issues")),
            ("Join official GitHub Discussions", getattr(self.constants, "github_discussions_link", "https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2/discussions")),
        ]

        # 3. Dynamic External Link Button Generation
        for label, url in resource_links:
            help_button = wx.Button(frame, label=label, pos=(-1, current_y), size=(220, 30))
            
            # Bound the lambda environment execution target safely using fixed parameter signatures
            help_button.Bind(wx.EVT_BUTTON, lambda event, target_url=url: webbrowser.open(target_url))
            help_button.Centre(wx.HORIZONTAL)
            
            # Step the coordinate down for the next item element sequence
            current_y += button_spacing
        gemini_button = wx.Button(frame, label="✨ Ask Gemini", pos=(-1, current_y), size=(220, 30))
        gemini_button.Bind(wx.EVT_BUTTON, self.on_gemini_help)
        gemini_button.Centre(wx.HORIZONTAL)

        current_y += button_spacing
        # 4. Return to Main Menu Action Button
        current_y += 10  # Add a slight visual separation gap before the close action button
        return_button = wx.Button(frame, label="Return to Main Menu", pos=(-1, current_y), size=(160, 30))
        return_button.Bind(wx.EVT_BUTTON, lambda event: frame.Close())
        return_button.Centre(wx.HORIZONTAL)

        # Automatically wrap structural layout scaling to avoid text truncation on varied OS platforms
        frame.SetSize((-1, return_button.GetPosition()[1] + return_button.GetSize()[1] + 45))


    def on_gemini_help(self, event: wx.Event):
            import webview # Import here to avoid slowing down OCLP startup
            
            logging.info("- Launching Gemini AI Assistant (pywebview)")
            
            # Create a sleek, floating window
            window = webview.create_window(
                title='Gemini AI Assistant',
                url='https://gemini.google.com',
                width=500,
                height=850,
                confirm_close=False,
                background_color='#ffffff'
            )
            
            # start() is blocking by default, but in a wxPython app, 
            # it usually needs to run in its own flow.
            webview.start()