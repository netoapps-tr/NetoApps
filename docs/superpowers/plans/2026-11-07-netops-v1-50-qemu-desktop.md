# NetOps v1.50 QEMU Virtual Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the PC-side v1.50 foundation with a bounded QEMU virtual desktop that can be controlled from NetOps without touching Android or the host Windows session.

**Architecture:** Keep QEMU behind a small `neto_virtual_desktop.py` manager. The manager resolves only known QEMU and disk locations, clamps resources, launches an owned child process, and uses snapshot mode by default. The existing assistant command router exposes Turkish start/status/stop/restart commands and returns a readable fallback when QEMU or an image is unavailable. Startup bypass is opt-in through the existing settings path so the current UI remains stable.

**Tech Stack:** Python 3, Tk/CustomTkinter command router, PowerShell QEMU launcher, pytest, QEMU x86_64.

**Spec:** User request in the conversation: complete v1.50 before reconnecting the phone, keep QEMU, avoid host/device crashes, and make the virtual desktop controllable from NetOps.

## Global Constraints

- v1.50 PC foundation only; Android/ADB/Wi-Fi device work is deferred.
- QEMU resource defaults are 1024 MB RAM and 2 vCPUs; accepted bounds are 512-4096 MB and 1-4 vCPUs.
- Snapshot mode is enabled by default; no arbitrary shell command or arbitrary QEMU arguments are accepted.
- A missing QEMU binary or disk image must produce a Turkish status response, not crash NetOps.
- The host Windows session and unrelated processes must never be stopped by the virtual desktop manager.
- Existing UI, Now Playing, startup assets, and unrelated working-tree changes are preserved.

## Review Focus

- QEMU is absent: command returns a clear unavailable state and NetOps remains open.
- Disk image is absent or outside the configured project locations: start is rejected without spawning.
- Start is requested twice: the existing owned process is reused instead of a second VM.
- Stop is requested after the process exits: it is a harmless no-op and reports stopped.
- Startup bypass is enabled: the main window is shown and the existing callback runs without a nested event loop.

---

### Task 1: Release Metadata and Direct Startup

**Files:**
- Modify: `neto_version.py`
- Modify: `config.py`
- Modify: `asistan beta.py`
- Modify: `tests/test_regressions.py`
- Modify: `tests/test_launch_surface.py`

**Interfaces:**
- Produces `APP_VERSION == "1.50.0"` and a direct-start setting that preserves the existing `on_started` callback path.

- [x] **Step 1: Write failing tests** for the v1.50 version and direct-start conditional.
- [x] **Step 2: Run the focused tests and confirm they fail because the repository is still on v1.42 and the unconditional launch gate remains.
- [x] **Step 3: Update release metadata and route startup through a safe direct-start branch while preserving the old launch gate when disabled.
- [x] **Step 4: Run the focused tests and confirm they pass.

### Task 2: Safe QEMU Virtual Desktop Manager

**Files:**
- Create: `neto_virtual_desktop.py`
- Create: `tests/test_virtual_desktop.py`
- Modify: `netops_os/scripts/run-qemu.ps1`

**Interfaces:**
- Produces `VirtualDesktopConfig`, `build_qemu_command(config, qemu_path, disk_path)`, and `VirtualDesktopManager.start()`, `.status()`, `.stop()`, `.restart()`.

- [x] **Step 1: Write failing unit tests** for command construction, resource clamping, missing dependencies, duplicate start, and owned-process stop.
- [x] **Step 2: Run `python -m pytest -q tests/test_virtual_desktop.py` and confirm the tests fail because the manager does not exist.
- [x] **Step 3: Implement the bounded manager with no shell invocation, snapshot-first disk handling, safe log output, and owned-process lifecycle.
- [x] **Step 4: Align the PowerShell launcher defaults and parameter bounds with the manager.
- [x] **Step 5: Run the focused tests and confirm they pass.

### Task 3: NetOps Command Integration

**Files:**
- Modify: `asistan beta.py`
- Modify: `tests/test_virtual_desktop_commands.py`

**Interfaces:**
- Consumes `neto_virtual_desktop.get_manager()` and produces Turkish responses for `sanal masaustu baslat`, `sanal masaustu durumu`, `sanal masaustu durdur`, and `sanal masaustu yeniden baslat` plus accented variants.

- [x] **Step 1: Write failing command-routing tests** using a fake manager and assert the router returns the manager result.
- [x] **Step 2: Run the focused tests and confirm they fail because the command branch is absent.
- [x] **Step 3: Add a narrow command helper before generic AI/web routing; keep dangerous-command confirmation and existing routes unchanged.
- [x] **Step 4: Run the focused command tests and confirm they pass.

### Task 4: Full Verification and Runtime Smoke Check

**Files:**
- Modify only files required by test failures.

- [x] **Step 1: Run `python -m py_compile "asistan beta.py" "neto_virtual_desktop.py" "neto_version.py"`.
- [x] **Step 2: Run `python -m pytest -q tests` and record the full result: `183 passed, 1 skipped`.
- [x] **Step 3: Run the application in `.py` mode with the virtual desktop unavailable and confirm it remains open; do not connect a phone. The process reached `mainloop`; the borderless window was not exposed by the Windows window inventory.
- [x] **Step 4: Review the diff for accidental UI, Android, or unrelated-file changes.

