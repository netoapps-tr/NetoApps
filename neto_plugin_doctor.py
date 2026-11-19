"""NetoPluginDoctor: non-destructive health checks for installed .nops plugins."""
from __future__ import annotations

import py_compile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neto_plugin_api import NetOpsPluginAPI
from neto_plugin_manager import NetOpsPluginManager


@dataclass
class PluginDoctorReport:
    plugin_count: int = 0
    passed: int = 0
    failed: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plugin_count": self.plugin_count,
            "passed": self.passed,
            "failed": self.failed,
            "findings": list(self.findings),
        }


class NetoPluginDoctor:
    """Checks plugins without invoking any system action handler."""

    def __init__(self, plugin_dir: str | Path | None = None) -> None:
        self.manager = NetOpsPluginManager(plugin_dir)

    def run(self) -> PluginDoctorReport:
        report = PluginDoctorReport()
        plugins = self.manager.discover()
        report.plugin_count = len(plugins)
        safe_api = NetOpsPluginAPI(
            handlers={
                "open_panel": lambda *_args, **_kwargs: None,
                "system_status": lambda: None,
                "launch_program": lambda *_args, **_kwargs: None,
                "set_volume": lambda *_args, **_kwargs: None,
                "move_window": lambda *_args, **_kwargs: None,
            }
        )
        for plugin in plugins:
            errors: list[str] = []
            if not plugin.scan.safe_to_review:
                errors.append("kritik güvenlik bulgusu")
            entry = plugin.path / plugin.manifest.entry
            if not entry.is_file():
                errors.append("entry dosyası eksik")
            elif entry.suffix.lower() == ".py":
                try:
                    py_compile.compile(str(entry), doraise=True)
                except py_compile.PyCompileError as exc:
                    errors.append(f"derleme hatası: {exc.msg}")
            if not errors:
                activation = self.manager.activate(plugin.manifest.plugin_id, safe_api)
                if not activation.get("ok"):
                    errors.append(f"kayıt hatası: {activation.get('error')}")
            if errors:
                report.failed += 1
                report.findings.append({"id": plugin.manifest.plugin_id, "errors": errors})
            else:
                report.passed += 1
        return report


__all__ = ["NetoPluginDoctor", "PluginDoctorReport"]
