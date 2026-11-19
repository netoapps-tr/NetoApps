# NetOps Native Desktop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AI-chat-looking home surface of the Windows NetOps application with a compact, utility-first desktop dashboard while preserving existing actions and integrations.

**Architecture:** Add a dependency-light CustomTkinter surface builder in `neto_desktop_surface.py`. The existing application remains the owner of callbacks and state; it passes those callbacks into the new surface and toggles the surface beside the existing chat view. No OS, QEMU, ISO, boot, or guest-system code is changed.

**Tech Stack:** Python 3.12, CustomTkinter, existing NetOps palette and callback functions, pytest.

**Spec:** User request in the current chat: desktop application only; open-source utility-app visual language; no AI-chat home screen.

## Global Constraints

- Desktop application scope only; do not modify `netops_os`, QEMU, ISO, Debian, bootloader, or recovery guest code.
- Keep the current Python source launch path; do not build or launch an EXE.
- Preserve existing command, device, Remote, Now Playing, automation, settings, and chat callbacks.
- Use compact rectangular utility controls; avoid oversized hero copy, decorative AI branding, and redundant icons.
- The new surface must remain usable when the window narrows.

## Review Focus

- A narrow window must keep dashboard cards readable instead of clipping or pushing the input bar away.
- Opening chat must hide the dashboard and show the existing chat/input surfaces.
- Existing callback names must remain callable from the dashboard.
- Theme colors must come from the current palette and refresh without a hard-coded theme fork.
- Importing the new module must work in the test environment without starting Tk or network services.

### Task 1: Native Surface Contract

**Files:**
- Create: `neto_desktop_surface.py`
- Create: `tests/test_desktop_surface.py`

**Interfaces:**
- Produces `navigation_items()`, `dashboard_cards()`, `dashboard_copy(locale="tr")`, `layout_contract()`, and `build_native_dashboard(ctk, parent, palette, callbacks=None)`.

- [ ] **Step 1: Write failing contract tests**
- [ ] **Step 2: Run `pytest tests/test_desktop_surface.py -q` and confirm the missing-module failure**
- [ ] **Step 3: Implement the pure contract helpers and the CustomTkinter builder**
- [ ] **Step 4: Run the focused tests and confirm they pass**

### Task 2: Main Window Integration

**Files:**
- Modify: `asistan beta.py` near the existing home hero construction and `_neto_sohbet_ekrani_ac`
- Modify: `tests/test_desktop_surface.py`

**Interfaces:**
- Consumes `build_native_dashboard(...)` and the existing NetOps callbacks.
- Produces `home_dashboard_surface` and `show_home_dashboard()` globals for safe view switching.

- [ ] **Step 1: Add source-level integration assertions before changing the main file**
- [ ] **Step 2: Run the focused tests and confirm they fail on the missing integration hook**
- [ ] **Step 3: Build the dashboard with existing callbacks and switch home/chat visibility without changing the command engine**
- [ ] **Step 4: Run focused tests and compile the modified modules**

### Task 3: Regression Verification

**Files:**
- No new production files.

- [ ] **Step 1: Run the desktop-surface tests**
- [ ] **Step 2: Run the existing UI, command, device, Remote, Now Playing, and recovery tests**
- [ ] **Step 3: Run `py_compile` for the changed Python files**
- [ ] **Step 4: Launch the source app with Python 3.12 and verify it reaches the main window without opening an EXE**

