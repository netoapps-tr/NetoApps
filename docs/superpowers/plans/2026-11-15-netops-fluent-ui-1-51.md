# NetOps 1.51 Fluent UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the desktop application’s visual shell with the open-source PyQt6-Fluent-Widgets component library while keeping NetOps services behind stable callbacks.

**Architecture:** `netops_fluent_shell.py` owns the Qt6 window, navigation, pages, cards, status badges, and command input. A small `FluentBackend` adapter supplies device, media, automation, system, and command actions. The existing CustomTkinter application remains available as a rollback path until each service page is verified.

**Tech Stack:** Python 3.12, PyQt6 6.11.0, PyQt6-Fluent-Widgets 1.11.3, existing NetOps service modules, pytest.

**Spec:** Current user request for NetOps 1.51: use a real open-source component library, do not hand-write a CSS-like visual system, preserve Cihazlar, Otomasyon, Now Playing, Sistem Durumu, and Komut Konsolu.

## Global Constraints

- Use `PyQt6-Fluent-Widgets` components instead of custom CSS or a custom design system.
- Keep `PyQt6`, `PyQt6-Qt6`, and `PyQt6-WebEngine` pinned at `6.11.0`.
- Preserve existing backend behavior through callbacks and adapter methods.
- Do not modify NetOps OS, QEMU, ISO, Debian, boot, or guest-system files.
- Keep the source `.py` launch path and provide an explicit legacy fallback while migration is verified.

## Review Focus

- Qt startup must not import or start a second event loop.
- The command input must remain responsive when a backend action is slow or unavailable.
- Navigation must show a safe status page when a service callback is missing.
- Cards and badges must use library components, not custom CSS classes.
- Existing PyQt6 WebEngine imports must remain compatible with the pinned Qt runtime.

### Task 1: Fluent Shell Contract

**Files:**
- Create: `netops_fluent_shell.py`
- Create: `tests/test_fluent_shell.py`

**Interfaces:**
- `FluentBackend` callback adapter.
- `fluent_navigation_items()` and `fluent_page_keys()` pure contracts.
- `NetOpsFluentWindow` using `NavigationInterface`, `CardWidget`, `InfoBadge`, and `LineEdit`.

- [ ] Write failing contract and component tests.
- [ ] Run the focused tests and confirm the missing-module failure.
- [ ] Implement the shell and safe callback adapter.
- [ ] Run focused tests and compile the module.

### Task 2: Backend Adapter

**Files:**
- Create: `netops_fluent_backend.py`
- Create: `tests/test_fluent_backend.py`

**Interfaces:**
- Read-only system snapshot provider.
- Device, Now Playing, automation, and command callback wrappers.

- [ ] Write failing adapter tests.
- [ ] Implement dependency-tolerant adapter methods.
- [ ] Run adapter and shell tests.

### Task 3: Safe Launch Route

**Files:**
- Modify: `asistan beta.py` only at the launch boundary.
- Modify: `requirements_live.txt` to pin the Fluent package.
- Create: `tests/test_fluent_launch_route.py`.

- [ ] Add an opt-in `NETOPS_FLUENT_UI=1` launch branch first.
- [ ] Verify the legacy CustomTkinter path remains the default during migration.
- [ ] Launch the Fluent source path with Python 3.12 and check the window.
- [ ] Promote the Fluent path to the 1.51 default only after service smoke tests pass.

