# NetOps Aider Guardrails

This project is the NetOps desktop assistant.

Rules for Aider:

- Do not rewrite the whole app.
- Do not delete user files, generated releases, installers, media files, or backups.
- Do not edit API keys or write secrets into Python files.
- Keep changes small and focused.
- Before editing, read the relevant file and explain the intended change.
- After Python edits, run:

```powershell
python -m py_compile "asistan beta.py"
```

- For related modules, compile them too:

```powershell
python -m py_compile "neto_settings_page.py" "neto_system_control.py" "neto_motion_engine_v2.py"
```

- Preserve the old sidebar UI unless the user explicitly asks for a redesign.
- Avoid broad refactors in `asistan beta.py`; it is large and fragile.
- Prefer adding adapter modules over mixing provider code directly into UI files.
- If a change touches timers, threads, UI callbacks, or process control, handle destroyed widgets and exceptions safely.
- Never expose raw API keys in logs, chat output, screenshots, or config files.
