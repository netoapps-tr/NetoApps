# Astryx Desktop Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the Astryx visual language to the existing NetOps CustomTkinter desktop application without replacing its working features or introducing a React runtime.

**Architecture:** Add a small, dependency-free Astryx token and style module, map it into the existing Fluent surface pipeline, and update the main desktop surfaces through existing palette refresh hooks. Keep Astryx source cloned outside the NetOps repository as a reference only.

**Tech Stack:** Python 3, CustomTkinter, Tkinter, existing NetOps theme/runtime modules, pytest.

**Spec:** User request: apply the locally referenced Astryx Design System style to the NetOps desktop executable.

## Global Constraints

- Preserve the current CustomTkinter architecture and all existing command callbacks.
- Do not add React, StyleX, Node, or a browser runtime to the desktop executable.
- Preserve Cihazlar, Now Playing, sohbet, ayarlar, startup sound, and existing window controls.
- Keep geometry stable during hover and active-state changes; no layout-changing hover effects.
- Keep the Astryx reference repository outside the NetOps repository.

## Review Focus

- Existing `hafiza.json` theme values: old saved values must still load safely.
- Narrow windows: sidebar labels and chat input must not clip or push the content area.
- Now Playing and Cihazlar: palette refresh must not destroy their live widgets or callbacks.
- Light theme: text and controls must remain readable with the new tokens.
- Frozen EXE mode: the new module must be bundled by the existing build script.

### Task 1: Astryx Token Layer

**Files:**
- Create: `neto_astryx_design.py`
- Modify: `neto_fluent_design.py`
- Test: `tests/test_astryx_design.py`

**Interfaces:**
- Produces `ASTRYX_DARK`, `ASTRYX_LIGHT`, `ASTRYX_RADII`, `astryx_palette()`, `astryx_control_style()`, `astryx_card_style()`, and `astryx_input_style()`.
- Existing Fluent helpers remain import-compatible.

- [ ] Write failing tests for the required Astryx tokens, contrast roles, stable radii, and style helper output.
- [ ] Run the focused tests and verify they fail because the module does not exist.
- [ ] Implement the token module and make the existing Fluent helpers use the compatible token values without changing public names.
- [ ] Run the focused tests and verify they pass.

### Task 2: Main Desktop Surface Mapping

**Files:**
- Modify: `asistan beta.py`
- Modify: `temalar.py`
- Modify: `config.py`
- Test: `tests/test_astryx_design.py`

**Interfaces:**
- Existing `aktif_palet` and `_neto_palet_uret()` remain the single runtime palette source.

- [ ] Add a failing source-level test proving the Astryx token layer is the default surface palette and that existing saved Fluent values remain accepted.
- [ ] Run the focused test and verify it fails before the mapping exists.
- [ ] Map the Astryx palette into the existing surface pipeline, preserving Fluent aliases and current settings behavior.
- [ ] Refine the main navigation, cards, metrics, input bar, and active controls through palette/style roles only; do not alter command callbacks.
- [ ] Run focused UI/source tests and verify they pass.

### Task 3: Settings and Frozen Build Coverage

**Files:**
- Modify: `neto_settings_page.py`
- Modify: `BUILD_EXE.ps1` only if the new module is not already collected.
- Test: `tests/test_astryx_design.py`, existing UI tests.

- [ ] Add a failing test for the settings surface label and build inclusion of the new module.
- [ ] Run the focused test and verify the expected failure.
- [ ] Expose the Astryx style as the current design language while retaining the old Fluent label as a compatibility alias.
- [ ] Ensure the build script includes `neto_astryx_design.py`.
- [ ] Run `python -m py_compile` on changed Python files and the full test suite.

### Task 4: Visual Verification

**Files:**
- No additional source files.

- [ ] Launch `asistan beta.py` in source mode.
- [ ] Check the main desktop at normal and narrow window sizes.
- [ ] Open Cihazlar, Now Playing, Otomasyon, and Ayarlar to confirm their controls remain reachable.
- [ ] Capture the final state and record any residual limitation instead of claiming completion without evidence.
