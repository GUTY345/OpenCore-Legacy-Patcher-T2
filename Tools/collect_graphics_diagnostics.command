#!/bin/bash
# =============================================================================
# collect_graphics_diagnostics.command
# READ-ONLY — Collects GPU/display diagnostic logs for MacBookPro14,3
# =============================================================================
# Safety: This script does NOT modify any system files, NVRAM, snapshots, or EFI.
# All output is written to a timestamped directory.
# =============================================================================

set -euo pipefail

TIMESTAMP=$(date "+%Y-%m-%d-%H-%M-%S")
OUTPUT_DIR="${HOME}/Desktop/GPU-Diagnostics-${TIMESTAMP}"

echo "============================================="
echo "  GPU / Display Diagnostics — MacBookPro14,3"
echo "============================================="
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo ""

mkdir -p "${OUTPUT_DIR}"

# --- System Info ---
echo ">>> Collecting system info..."
sw_vers > "${OUTPUT_DIR}/sw_vers.txt" 2>&1
uname -a > "${OUTPUT_DIR}/uname.txt" 2>&1
system_profiler SPHardwareDataType > "${OUTPUT_DIR}/hardware.txt" 2>&1

# --- GPU Info ---
echo ">>> Collecting GPU info..."
system_profiler SPDisplaysDataType > "${OUTPUT_DIR}/gpu_displays.txt" 2>&1

# --- IORegistry GPU dump ---
echo ">>> Dumping IORegistry GPU entries..."
ioreg -l -w 0 | grep -i -A 20 "class.*GPU\|class.*Display\|class.*Framebuffer\|class.*GFX\|IOGPUFamily" > "${OUTPUT_DIR}/ioreg_gpu.txt" 2>&1 || true

# --- Kernel GPU logs ---
echo ">>> Collecting kernel GPU logs..."
log show --predicate 'subsystem == "com.apple.gpu" OR subsystem == "com.apple.iokit" OR eventMessage CONTAINS "GPU" OR eventMessage CONTAINS "gfx" OR eventMessage CONTAINS "Framebuffer"' --last 1h --style compact > "${OUTPUT_DIR}/kernel_gpu_logs.txt" 2>&1 || true

# --- WindowServer logs ---
echo ">>> Collecting WindowServer logs..."
log show --predicate 'process == "WindowServer"' --last 30m --style compact > "${OUTPUT_DIR}/windowserver_logs.txt" 2>&1 || true

# --- CoreDisplay logs ---
echo ">>> Collecting CoreDisplay logs..."
log show --predicate 'subsystem == "com.apple.CoreDisplay" OR process == "displaypolicyd"' --last 30m --style compact > "${OUTPUT_DIR}/coredisplay_logs.txt" 2>&1 || true

# --- SecurityAgent / loginwindow logs (boot/login issues) ---
echo ">>> Collecting SecurityAgent/loginwindow logs..."
log show --predicate 'process == "SecurityAgent" OR process == "loginwindow"' --last 30m --style compact > "${OUTPUT_DIR}/login_logs.txt" 2>&1 || true

# --- Kext list (graphics-related) ---
echo ">>> Listing loaded graphics kexts..."
kextstat 2>/dev/null | grep -iE "gpu|graphics|display|framebuffer|whatevergreen|radeon|amd|intel" > "${OUTPUT_DIR}/graphics_kexts.txt" 2>&1 || true

# --- Boot args ---
echo ">>> Checking boot-args..."
nvram boot-args 2>/dev/null > "${OUTPUT_DIR}/boot_args.txt" 2>&1 || echo "No boot-args set" > "${OUTPUT_DIR}/boot_args.txt"

# --- Summary ---
echo ""
echo "============================================="
echo "  Collection complete"
echo "============================================="
echo "Output saved to: ${OUTPUT_DIR}"
echo ""
echo "Files collected:"
ls -la "${OUTPUT_DIR}/"
echo ""
echo "Please share this directory for analysis."
