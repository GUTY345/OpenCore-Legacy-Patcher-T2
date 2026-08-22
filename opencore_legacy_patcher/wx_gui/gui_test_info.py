"""
gui_test_info.py: Dialog for displaying detailed explanations of all OCLP test levels and patches
"""

import wx
import wx.adv
import logging

from .. import constants
from . import gui_support


class TestExplanationDialog(wx.Dialog):
    """
    Dialog providing clear and comprehensive explanations of all build profiles,
    experimental test levels (Level B, Level C, Level D), boot-args, Wi-Fi, Audio, and T1 root patches.
    """

    def __init__(self, parent: wx.Window, global_constants: constants.Constants, initial_tab: int = 0) -> None:
        super().__init__(
            parent,
            title="Guida & Spiegazione Livelli di Test, Wi-Fi, Audio e Patch",
            size=(680, 580),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.constants: constants.Constants = global_constants
        self.Centre()

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header Title
        title_label = wx.StaticText(panel, label="📘 Guida Completa ai Livelli di Test & Patch")
        title_label.SetFont(gui_support.font_factory(16, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(title_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 12)

        subtitle_label = wx.StaticText(
            panel,
            label=f"Configurazione per {self.constants.custom_model or self.constants.computer.real_model} — macOS Tahoe / T1 Experimental"
        )
        subtitle_label.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
        subtitle_label.SetForegroundColour(wx.Colour(120, 120, 120))
        main_sizer.Add(subtitle_label, 0, wx.BOTTOM | wx.ALIGN_CENTER_HORIZONTAL, 10)

        # Notebook (Tabs) for categories
        notebook = wx.Notebook(panel)

        # --- TAB 1: Livelli di Build EFI ---
        tab_builds = wx.Panel(notebook)
        tab_builds_sizer = wx.BoxSizer(wx.VERTICAL)
        text_builds = wx.TextCtrl(
            tab_builds,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        text_builds.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
        text_builds.SetValue(self._get_builds_text())
        tab_builds_sizer.Add(text_builds, 1, wx.EXPAND | wx.ALL, 8)
        tab_builds.SetSizer(tab_builds_sizer)
        notebook.AddPage(tab_builds, "🧪 Livelli di Build (A/B/C/D)")

        # --- TAB 2: Boot-args & GPU Dual-Graphics ---
        tab_bootargs = wx.Panel(notebook)
        tab_bootargs_sizer = wx.BoxSizer(wx.VERTICAL)
        text_bootargs = wx.TextCtrl(
            tab_bootargs,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        text_bootargs.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
        text_bootargs.SetValue(self._get_bootargs_text())
        tab_bootargs_sizer.Add(text_bootargs, 1, wx.EXPAND | wx.ALL, 8)
        tab_bootargs.SetSizer(tab_bootargs_sizer)
        notebook.AddPage(tab_bootargs, "🚀 Boot-args & GPU")

        # --- TAB 3: T1 Chip & Password Login ---
        tab_t1 = wx.Panel(notebook)
        tab_t1_sizer = wx.BoxSizer(wx.VERTICAL)
        text_t1 = wx.TextCtrl(
            tab_t1,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        text_t1.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
        text_t1.SetValue(self._get_t1_text())
        tab_t1_sizer.Add(text_t1, 1, wx.EXPAND | wx.ALL, 8)
        tab_t1.SetSizer(tab_t1_sizer)
        notebook.AddPage(tab_t1, "🔐 T1 & Login Tahoe")

        # --- TAB 4: Wi-Fi & Audio (Tahoe Fixes) ---
        tab_wifi_audio = wx.Panel(notebook)
        tab_wifi_audio_sizer = wx.BoxSizer(wx.VERTICAL)
        text_wifi_audio = wx.TextCtrl(
            tab_wifi_audio,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        text_wifi_audio.SetFont(gui_support.font_factory(11, wx.FONTWEIGHT_NORMAL))
        text_wifi_audio.SetValue(self._get_wifi_audio_text())
        tab_wifi_audio_sizer.Add(text_wifi_audio, 1, wx.EXPAND | wx.ALL, 8)
        tab_wifi_audio.SetSizer(tab_wifi_audio_sizer)
        notebook.AddPage(tab_wifi_audio, "🌐 Wi-Fi & 🔊 Audio (Tahoe)")

        # Select requested tab
        if 0 <= initial_tab < notebook.GetPageCount():
            notebook.SetSelection(initial_tab)

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        # Bottom Close Button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_close = wx.Button(panel, label="Chiudi", size=(120, 32))
        btn_close.SetFont(gui_support.font_factory(12, wx.FONTWEIGHT_NORMAL))
        btn_close.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_OK))
        button_sizer.Add(btn_close, 0, wx.ALL, 10)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(main_sizer)
        panel.Layout()

    def _get_builds_text(self) -> str:
        return """============================================================
LIVELLI DI BUILD OPENCORE (PROFILI)
============================================================

1. 🟢 BUILD STANDARD / SAFE:
   • Scopo: Configurazione OpenCore stock e stabile certificata da Dortania.
   • SMBIOS: Mantiene l'SMBIOS nativo del Mac.
   • Target: Uso quotidiano su versioni di macOS supportate e validate.

------------------------------------------------------------

2. 🧪 [LEVEL-B] EXPERIMENTAL GPU:
   • Scopo: Diagnostica e isolamento delle problematiche grafiche (GPU).
   • Kext: Inietta e attiva WhateverGreen.kext versione 1.7.0.
   • Boot-arg: Inietta '-wegnoegpu' per disabilitare l'alimentazione/switching
     della dGPU e isolare test sulla sola grafica integrata Intel.

------------------------------------------------------------

3. 🧪 [LEVEL-C] EXPERIMENTAL TAHOE (MacBookPro14,3):
   • Goal: Experimental support for macOS 26 (Tahoe) maintaining
     l'identità hardware nativa del MacBook Pro 2017 (T1).
   • Boot-args automatici:
     - 'dart=0': Risolve mapping IOMMU e periferiche Wi-Fi/Bluetooth.
     - 'agdpmod=ignore': Bypassa Apple Graphics Device Policy ed evita
       lo schermo nero all'avvio su MacBookPro14,3 (Polaris + Kaby Lake).
     - 'cryptex=0 cs_allow_invalid=1': Permette il caricamento del kernel.
   • SMBIOS: Nativo ('MacBookPro14,3'), senza spoofing.

------------------------------------------------------------

4. 🧪 [LEVEL-C] EXPERIMENTAL SPOOF T2:
   • Scopo: Spoofa l'SMBIOS come 'MacBookPro16,1' / 'MacBookPro16,2' (Mac T2)
     per verificare il comportamento dell'installer e del kernel Tahoe.
   • Bypass T2: Bypassa il blocco di abort T2 all'interno dell'app OCLP.
   • Includes all Level C boot-args (dart=0, agdpmod=ignore, cryptex=0).

------------------------------------------------------------

5. 🧪 [LEVEL-D] EXPERIMENTAL ALL-IN-ONE (Wi-Fi + Audio + GPU + T1):
   • Scopo: Profilo COMPLETO e integrato con tutte le patch attive in contemporanea.
   • Wi-Fi: Attiva IOSkywalkFamily, IO80211FamilyLegacy, AirportBrcmFixup,
     blocco driver nativo Skywalk e boot-arg 'ipc_control_port_options=0 amfi=0x80'.
   • Audio: Attiva AppleALC.kext + 'alcid=13' (codec HDEF di MacBookPro14,3).
   • GPU: Dual-GPU Kaby Lake + Polaris con 'agdpmod=pikera' e 'dart=0'.
   • T1 Security: Login sicuro con sola password + supporto account iCloud/Apple ID.
"""

    def _get_bootargs_text(self) -> str:
        return """============================================================
SPECIFIC BOOT-ARGS EXPLANATION FOR MACBOOKPRO14,3
============================================================

• dart=0
  Disables IOMMU / VT-d virtualization at the macOS kernel level.
  Fondamentale su MacBookPro14,3 e Mac 2017 per evitare crash del driver
  Wi-Fi Broadcom (14E4:43BA), Bluetooth e controller PCIe su macOS Tahoe.

• agdpmod=ignore (o agdpmod=pikera in LEVEL-D)
  Bypassa i controlli di AppleGraphicsDevicePolicy (AGDP).
  Nei MacBook Pro con doppia GPU (Intel HD 630 + AMD Polaris), AGDP
  tende a disattivare le uscite video all'avvio di WindowServer,
  causando lo schermo nero. La patch forza il driver a mantenere
  attive le connessioni framebuffer.

• ipc_control_port_options=0
  Disabilita il controllo restrittivo dei messaggi IPC Mach port introdotto
  in macOS Tahoe. Indispensabile per consentire la comunicazione tra i demoni
  di rete 'wifip2pd' / 'airportd' e il kernel senza causare crash o bootloop.

• amfi=0x80
  Permette ai binari patchati nel volume di root (Wi-Fi, grafica, framework)
  di essere eseguiti dal kernel senza essere bloccati da Apple Mobile File Integrity.

• alcid=13
  Inietta il Layout ID audio 13 per AppleALC.kext, corrispondente al codec
  analogico di MacBookPro14,3 (Realtek ALC / AppleHDA).

• cryptex=0 & cs_allow_invalid=1
  Disabilita l'obbligo di autenticazione crittografica Cryptex e consente
  l'avvio del kernel con kext e binari modificati.

• -lilubetaall
  Forza Lilu e tutti i suoi plugin (AppleALC, WhateverGreen, AirportBrcmFixup)
  a caricarsi anche su versioni di macOS più recenti (Tahoe 26.x).
"""

    def _get_t1_text(self) -> str:
        return """============================================================
T1 SECURITY CHIP & AUTENTICAZIONE SU MACOS TAHOE (26.x)
============================================================

• Perché Touch ID non è attivo su Tahoe?
  Apple ha rimosso completamente il supporto al bridge USB del chip T1
  nelle ultime versioni di macOS. Forzare i vecchi kext e framework di
  Ventura (AppleKeyStore 13.6, biometrickitd, SharedUtils 13.6) crea una
  grave incompatibilità ABI/IPC con i demoni di sicurezza nativi di Tahoe
  (securityd, LocalAuthentication, akd), bloccando le richieste di password
  in System Settings and Apple Account access.

• Come funziona la modalità Native Software Keystore su Tahoe?
  1. Preserva i driver kernel nativi di Tahoe (AppleKeyStore & AppleCredentialManager)
     eseguendoli in modalità software (CPU crypto Intel Kaby Lake).
  2. 100% restores PASSWORD authorization in System Settings.
  3. Consente la modifica e gestione delle password account e del portachiavi.
  4. Sblocca l'accesso ad Apple Account / iCloud grazie all'integrazione di
     AMFIPass (-amfipassbeta) e al bypass di attestazione (-oas_skip_attestation).
  5. Mantiene la Touch Bar (TouchBarServer / AppleHSSPISupport) pienamente stabile.

• Risultato:
  Autenticazione locale e cloud affidabili, sblocco lucchetti di sistema funzionante,
  Apple Account operativo, senza schermate nere o crash del SecurityAgent.
"""

    def _get_wifi_audio_text(self) -> str:
        return """============================================================
ANALISI & FUNZIONAMENTO DI WI-FI E AUDIO SU MACOS TAHOE
============================================================

🔊 COME FUNZIONA L'AUDIO SU TAHOE (OCLP-MOD & OCLP PLUS):
1. Problema:
   A partire da macOS 26 Tahoe, Apple ha rimosso completamente 'AppleHDA.kext'
   dal sistema operativo, rompendo l'audio analogico (altoparlanti interni,
   microfoni e jack cuffie) sui Mac senza chip T2.
2. Soluzione Integrata:
   • Lato Root Patcher: Il patchset 'ModernAudio' re-inietta 'AppleHDA.kext'
     in /System/Library/Extensions.
   • Lato EFI: Viene caricato 'AppleALC.kext' (v1.9.7) insieme a 'Lilu.kext',
     iniettando 'alcid=13' e '-lilubetaall'.
   • Risultato: CoreAudio riconosce correttamente il codec hardware e ripristina
     l'uscita e l'ingresso audio integrati.

------------------------------------------------------------

🌐 COME FUNZIONA IL WI-FI SU TAHOE (BROADCOM BCM943602 / 14E4:43BA):
1. Problema:
   Apple ha sostituito il sottosistema Wi-Fi tradizionale con la nuova
   architettura Skywalk, eliminando il supporto nativo per i chipset Broadcom.
2. Soluzione Integrata:
   • In OpenCore EFI (Kernel -> Block): Viene bloccato il driver nativo
     'com.apple.iokit.IOSkywalkFamily'.
   • In OpenCore EFI (Kernel -> Add): Vengono iniettati:
     - 'IOSkywalkFamily.kext' (v1.2.0)
     - 'IO80211FamilyLegacy.kext' (e plugin 'AirPortBrcmNIC.kext')
     - 'AirportBrcmFixup.kext' (con 'brcmfx-country=IT')
     - 'AMFIPass.kext'
   • Boot-args essenziali:
     - 'ipc_control_port_options=0': Previene il crash delle porte Mach IPC tra
       i demoni di rete 'wifip2pd' e il kernel Tahoe.
     - 'amfi=0x80': Permette l'esecuzione dei servizi di rete modificati.
   • Lato Root Patcher: Dopo il primo avvio, 'Install drivers and patches'
     applica il patchset 'ModernWireless' che fonde 'IO80211.framework' e
     'WiFiPeerToPeer.framework' nel volume di root.
"""
