        self._update_setting(self.settings[self._find_parent_for_key(label)][label]["variable"], value)
        if label == "Allow native models":
            if hasattr(self.parent, 'build_button') and self.parent.build_button:
                if gui_support.CheckProperties(self.constants).host_can_build() is True:
                    self.parent.build_button.Enable()
                else:
                    self.parent.build_button.Disable()
