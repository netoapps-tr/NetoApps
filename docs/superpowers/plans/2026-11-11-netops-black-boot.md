# NetOps Black Boot Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the installed NetOps OS boot view with a black NetOps logo screen that reports boot progress, while keeping Debian installer internals hidden during preview image creation and reducing avoidable packages/cache files.

**Architecture:** Keep the guest boot path in Plymouth and use the existing NetOps theme as the single source of truth for normal boots. Run the unattended installer without a visible guest display so its blue Debian UI cannot leak into the user-facing flow; the installed disk remains the bootable artifact. Package cleanup is limited to caches and explicitly nonessential preview packages.

**Tech Stack:** Debian preseed, shell scripts, Plymouth script themes, PowerShell/QEMU, pytest.

**Spec:** User request in the current conversation: black screen, NetOps logo, loading percentage, and fewer unnecessary OS files.

## Global Constraints

- The Windows host must not be repartitioned or modified by the guest build.
- The installed guest must continue to boot into the existing NetOps session.
- No arbitrary shell access is added to the OS or remote agent.
- The boot progress must be based on Plymouth boot progress events, not a fake timer.

## Review Focus

- Plymouth unavailable or unsupported progress events: the logo screen still renders without crashing; test in the theme text.
- Missing splash asset: build fails clearly instead of silently producing a blank boot.
- Installer display accidentally enabled: QEMU arguments keep the install display hidden; test the command construction.
- Package cleanup removing update-critical state: only apt caches/temp files are removed; test the cleanup commands.
- Existing OS boot path regression: autologin/session and remote-agent service declarations remain present; test the guest payload.

---

### Task 1: Lock the boot and packaging contract with tests

**Files:**
- Create: `tests/test_netops_boot_splash.py`
- Test: `tests/test_netops_boot_splash.py`

**Interfaces:**
- Consumes: `netops_os/guest/netops.script`, `netops_os/guest/install-netops-preview.sh`, `netops_os/scripts/build-netops-preview.ps1`.
- Produces: regression assertions for progress events, black theme behavior, hidden installer display, and safe cleanup.

- [ ] **Step 1: Write failing tests** for a Plymouth progress callback/percentage text, black background, hidden installer display, and cache-only cleanup.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_netops_boot_splash.py` and confirm the new assertions fail for the current files.

### Task 2: Implement the black progress boot theme

**Files:**
- Modify: `netops_os/guest/netops.script`
- Modify: `netops_os/guest/install-netops-preview.sh`

**Interfaces:**
- Consumes: the existing `netops-splash.png` and `netops.plymouth` theme registration.
- Produces: a black Plymouth screen with centered logo, a progress bar, and a percentage label updated by Plymouth boot progress events.

- [ ] **Step 1: Add the minimal Plymouth progress implementation** using `Plymouth.SetBootProgressFunction`, a bounded progress bar, and percentage text; keep a safe static logo fallback.
- [ ] **Step 2: Keep the NetOps theme selected and regenerate initramfs** through the existing install script.
- [ ] **Step 3: Add cache-only cleanup** after package installation: apt lists/cache and temporary payload files only; preserve package databases and runtime assets.
- [ ] **Step 4: Run the focused tests and inspect the changed shell/theme files.**

### Task 3: Hide the Debian installer UI during image creation

**Files:**
- Modify: `netops_os/scripts/build-netops-preview.ps1`

**Interfaces:**
- Consumes: existing unattended preseed install and `C:\NetOpsVM` artifact paths.
- Produces: installer QEMU process launched with no guest display, preventing the blue Debian installer screen from being shown to the user.

- [ ] **Step 1: Add the smallest QEMU argument change** to use `-display none` only for the unattended installer path; do not change normal `run-qemu.ps1` display behavior.
- [ ] **Step 2: Add a clear host-side progress message** so the user knows installation is active while the guest display is hidden.
- [ ] **Step 3: Run the focused tests and PowerShell parse validation.**

### Task 4: Verify the complete change

- [ ] **Step 1: Run** `python -m pytest -q tests/test_netops_boot_splash.py tests/test_netops_xfce.py`.
- [ ] **Step 2: Run** `python -m py_compile netops_os/guest/netops_app.py`.
- [ ] **Step 3: Run** a PowerShell syntax/load check for `netops_os/scripts/build-netops-preview.ps1` without starting QEMU.
- [ ] **Step 4: Report separately what is verified in source and what still requires rebuilding the guest image.**
