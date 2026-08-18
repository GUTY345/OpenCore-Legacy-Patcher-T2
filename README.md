<div align="center">
  <img src="https://github.com/dortania/OpenCore-Legacy-Patcher/blob/macos-next/docs/images/OC-Patcher.png"
       alt="OpenCore Patcher Logo" width="256" />

  <h1>OpenCore Legacy Patcher T2 — Experimental Tahoe Fork</h1>
</div>

# OpenCore Legacy Patcher T2 — Experimental Tahoe Fork

A community fork of [OpenCore Legacy Patcher T2](https://github.com/albert-mueller/OpenCore-Legacy-Patcher-T2) focused on experimental macOS Tahoe 26.x support for unsupported Intel Macs, with particular focus on the **MacBookPro14,3 (15-inch 2017 Touch Bar, T1)**.

> ⚠️ **EXPERIMENTAL SOFTWARE**
>
> This project is intended for testing and development. It is not production-ready. Always maintain a working installation and a reliable backup before testing.

## Current Focus

The primary development and testing target is:

- **MacBookPro14,3**
- 15-inch MacBook Pro (2017)
- Touch Bar / T1
- Intel HD Graphics 630
- AMD Radeon Pro 555 / Polaris
- macOS Tahoe 26.x

The current work focuses on making Tahoe usable while preserving the native hardware architecture wherever possible.

## MacBookPro14,3 Graphics Baseline

The current MBP14,3 graphics configuration uses a minimal root-patching approach.

The graphics baseline has been tested with:

- Internal display
- External display
- GPU acceleration
- Metal
- WindowServer
- Sleep / wake
- AMD Polaris GPU detection

The current approach avoids unnecessary GPU-disabling boot arguments and avoids replacing the native Tahoe Metal stack when it is not required.

### AMD Polaris

For MacBookPro14,3, the current root-patch configuration restores the required AMD graphics components from macOS 13.5.2:

- `AMD9500Controller.kext`
- `AMD10000Controller.kext`
- `AMDFramebuffer.kext`
- `AMDSupport.kext`

The native Tahoe Metal components remain in place.

> **Important:** This configuration is specific to the current MBP14,3 testing baseline and should not automatically be applied to other Mac models.

## OpenCore

This fork includes experimental OpenCore configuration and boot support required for Tahoe testing on unsupported Macs.

The project also follows the OpenCore fork used by the upstream OpenCore Legacy Patcher T2 project where applicable.

OpenCore configuration and payloads may change during development.

## Project Status

> 🚧 **Experimental — active development**

### MacBookPro14,3

- [x] Tahoe kernel/userspace boot
- [x] Internal display
- [x] External display
- [x] GPU detection
- [x] GPU acceleration
- [x] Metal
- [x] WindowServer
- [x] Sleep / wake testing
- [x] T1 functionality testing
- [ ] Complete long-term stability testing
- [ ] Broader hardware testing
- [ ] General release

A successful test on one MacBookPro14,3 does **not** imply compatibility with every MacBookPro14,3 configuration.

## TEST-D

The repository currently contains a TEST-D all-in-one EFI configuration used during development and hardware testing.

This EFI is intended for controlled testing and should not be considered a universal configuration.

## Relationship to OpenCore Legacy Patcher T2

This project is a fork of:

**albert-mueller/OpenCore-Legacy-Patcher-T2**

The upstream project provides the foundation for T2 support, Tahoe compatibility work, root patching, OpenCore integration and related functionality.

This fork adds experimental development and testing work focused primarily on the MacBookPro14,3.

## Important

Do not assume that patches designed for the MacBookPro14,3 are appropriate for other Macs.

Different Intel Macs may require completely different:

- GPU handling
- framebuffer configuration
- Metal patches
- boot arguments
- T1/T2 handling
- root patches
- OpenCore configuration

Testing should therefore be performed on a model-by-model basis.

## Installation

This project is experimental.

For development and testing, use the repository's build instructions:

[Build and run from source](./SOURCE.md)

Releases, when published, will contain the corresponding application and/or EFI payloads for the tested build.

## Support

This project is provided on an **AS-IS** basis.

When reporting an issue, provide:

- Mac model
- macOS version/build
- OpenCore version
- OCLP-T2 version/commit
- root-patch status
- OpenCore configuration
- relevant system logs
- panic/crash reports
- exact reproduction steps

## Credits

This project would not be possible without the work of:

- [Acidanthera](https://github.com/acidanthera)
- [Dortania](https://github.com/dortania)
- [Albert Müller](https://github.com/albert-mueller)
- Contributors to OpenCore Legacy Patcher
- Contributors to OpenCore Legacy Patcher T2
- The wider unsupported Mac development community

This fork is derived from the OpenCore Legacy Patcher T2 project and retains the upstream project's licensing and attribution.

## Disclaimer

This is experimental software.

Use it only if you understand the risks associated with modifying OpenCore, macOS system volumes, root patches, APFS snapshots and unsupported macOS installations.

Keep a known-good macOS installation available for recovery.

docs: fix source build link
