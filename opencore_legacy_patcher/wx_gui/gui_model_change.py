            defaults.GenerateDefaults(self.constants.custom_model, False, self.constants)
            if hasattr(self.parent, 'build_button') and self.parent.build_button:
                self.parent.build_button.Enable()
