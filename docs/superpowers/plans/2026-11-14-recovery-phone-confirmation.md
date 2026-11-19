# Recovery Phone Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `netops recovery` request phone confirmation before hiding the main NetOps window, play a warning sound on approval, and provide safe Recovery-side NetOps sound selection.

**Architecture:** Keep the authenticated Device Hub protocol and the existing Recovery surface. Add a small, pure confirmation state/command layer so worker-thread requests never mutate Tk directly. Centralize user-selected sound overrides in a small sound manager; the Recovery surface will expose a file-picker panel for warning, startup, and update sounds.

**Tech Stack:** Python 3.12, Tkinter/CustomTkinter, pygame mixer, authenticated WebSocket Device Hub, Termux CLI, pytest-compatible zero-argument tests.

**Spec:** User request in the 2026-11-14 conversation: Termux `netops recovery` must show a phone confirmation prompt, play `dragon-studio-notification-bell-sound-1-376885.mp3` as the warning, transition only after approval, and allow NetOps sounds to be changed from Recovery.

## Global Constraints

- Do not launch or build an EXE; validate the source `asistan beta.py` with Python 3.12.
- No arbitrary shell execution, root escalation, or destructive Recovery action is added.
- The main Tk window is hidden only after an explicit authenticated confirmation from the paired phone.
- All Tk mutations are scheduled on the Tk main loop with `root.after`.
- The warning sound must have a bundled fallback and a user override without modifying arbitrary project files.
- Recovery sound changes are explicit file-picker actions and remain local to the PC.

## Review Focus

- Repeated `netops recovery` requests must not create duplicate pending prompts or Recovery windows; test idempotence.
- `onayla` without a pending request must not enter Recovery; test rejection.
- Cancellation and unknown phone text must leave the main window visible; test both paths.
- Missing or unsupported audio files must fail safely without blocking Recovery; test fallback resolution.
- A worker-thread request must not call `withdraw()` directly; test deferred Tk scheduling.

---

### Task 1: Confirmation Contract

**Files:**
- Modify: `neto_recovery_surface.py`
- Test: `tests/test_recovery_mode.py`

**Interfaces:**
- Produces `is_recovery_confirmation(value: str) -> bool`.
- Produces `is_recovery_cancellation(value: str) -> bool`.
- Produces `recovery_confirmation_prompt() -> str`.

- [ ] **Step 1: Write failing tests** for accepted Turkish/English confirmation, cancellation, and the exact phone prompt text.
- [ ] **Step 2: Run the focused recovery tests** and verify the new helpers fail because they do not exist.
- [ ] **Step 3: Implement the pure helpers** with whitespace/case normalization and no side effects.
- [ ] **Step 4: Run the focused recovery tests** and verify they pass.

### Task 2: Safe Phone-Gated Transition

**Files:**
- Modify: `asistan beta.py`
- Test: `tests/test_recovery_mode.py`

**Interfaces:**
- Adds `_NETO_RECOVERY_CONFIRMATION_PENDING`.
- `neto_recovery_assistant_request(text, device_id)` returns a confirmation prompt for `/recovery Netops`, rejects approval without a pending request, and schedules the existing `neto_recovery_surface_launch_safe()` only after approval.

- [ ] **Step 1: Add failing source-level tests** for pending-state handling, approval gating, cancellation, and `root.after` scheduling.
- [ ] **Step 2: Run the tests** and verify they fail against the current immediate-launch behavior.
- [ ] **Step 3: Implement the pending confirmation state** and reset it on approval, cancellation, close, or launch failure.
- [ ] **Step 4: Run the tests** and verify the main UI remains visible before approval and is hidden only in the scheduled callback after approval.

### Task 3: Sound Override Manager

**Files:**
- Create: `neto_sound_manager.py`
- Modify: `asistan beta.py`
- Test: `tests/test_sound_manager.py`

**Interfaces:**
- `SOUND_ROLES = ("recovery_warning", "startup", "update")`.
- `resolve_sound(role: str, project_dir: str | Path = ".") -> Path | None`.
- `save_sound_override(role: str, source: str | Path, user_dir: str | Path | None = None) -> Path`.
- `clear_sound_override(role: str, user_dir: str | Path | None = None) -> None`.

- [ ] **Step 1: Write failing tests** for role validation, safe extension validation, copying an override into the user sound directory, and bundled fallback resolution.
- [ ] **Step 2: Run the tests** and verify the new module is missing.
- [ ] **Step 3: Implement the manager** using `config.get_user_data_dir()`, allowing only `.mp3`, `.wav`, and `.ogg`, with atomic replacement and no arbitrary destination paths.
- [ ] **Step 4: Copy the supplied MP3** to `assets/recovery-warning.mp3` as the bundled warning fallback.
- [ ] **Step 5: Update `ses_oynat` and the Recovery warning path** to resolve overrides first and bundled assets second.
- [ ] **Step 6: Update `BUILD_EXE.ps1` and `NetOps.spec`** so the warning asset is packaged for future builds without launching one now.
- [ ] **Step 7: Run sound-manager tests and compile checks** and verify all pass.

### Task 4: Recovery Sound Settings UI

**Files:**
- Modify: `neto_recovery_surface.py`
- Test: `tests/test_recovery_mode.py`

**Interfaces:**
- Recovery surface exposes `Sesleri Yönet`.
- Sound settings allow selecting/replacing `recovery_warning`, `startup`, and `update`, previewing the selected warning sound, and clearing an override.

- [ ] **Step 1: Write failing source-level tests** for the three sound roles, file-picker usage, and safe manager calls.
- [ ] **Step 2: Run the tests** and verify the controls are absent.
- [ ] **Step 3: Add the compact Recovery sound panel** using Tk file dialogs and main-loop-safe status messages; no arbitrary command field is added.
- [ ] **Step 4: Run the tests** and verify the panel contract passes.

### Task 5: Termux Confirmation UX and Documentation

**Files:**
- Modify: `mobile/termux/netops_shell.py`
- Modify: `mobile/termux/README.md`
- Test: `tests/test_termux_shell.py`

**Interfaces:**
- `netops recovery` sends `/recovery Netops` and prints the phone confirmation prompt.
- `netops ask onayla` confirms the pending request.
- `netops ask iptal` cancels it.
- Optional `netops recovery --confirm` is not added unless tests show a clear need; the two-step flow remains the default.

- [ ] **Step 1: Add failing CLI tests** for the two-step command examples and Turkish aliases.
- [ ] **Step 2: Run the focused Termux tests** and verify the new expectations fail if parser or help text is incomplete.
- [ ] **Step 3: Add the minimal CLI/help documentation** without adding arbitrary remote shell behavior.
- [ ] **Step 4: Run Termux tests and compile checks** and verify they pass.

### Task 6: End-to-End Source Verification

**Files:**
- Test: `tests/test_recovery_mode.py`, `tests/test_termux_shell.py`, `tests/test_sound_manager.py`

- [ ] **Step 1: Run all relevant zero-argument tests** with the available Python 3.12 environment.
- [ ] **Step 2: Run `py_compile`** for the changed source files.
- [ ] **Step 3: Start only `asistan beta.py`**, verify the WebSocket endpoint remains online, and confirm no EXE is launched.
- [ ] **Step 4: Use the connected RMX3890 Termux session** to run `netops recovery`, confirm the prompt, run `netops ask onayla`, verify the warning sound and Recovery surface, then run `netops ask recovery durum`.
- [ ] **Step 5: Report the exact tested flow and any dependency or permission limitation.**
