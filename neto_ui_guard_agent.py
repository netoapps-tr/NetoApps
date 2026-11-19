"""Read-only UI guard for NetOps screens and media text.

This agent reports regressions; it never rewrites widgets or changes animation settings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UIGuardReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: int = 0

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": len(self.warnings),
            "checks": self.checks,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


class NetOpsUIGuardAgent:
    """Checks UI contracts without importing or launching the GUI."""

    REQUIRED_MARKERS = (
        "def now_playing_idle_best_info",
        "def now_playing_idle_apply_info",
        "def now_playing_idle_canvas_draw_text",
        "def now_playing_idle_turkish_date",
        "def now_playing_overlay_update",
    )
    ERROR_PATTERNS = (
        r"Traceback \(most recent call last\)",
        r"KeyError: ['\"](?:text_main|title|artist|status)['\"]",
        r"\[TK_CALLBACK_EXCEPTION\]",
        r"\[IDLE_CANVAS_TEXT_ERROR\]",
    )

    UPDATE_MARKERS = (
        'REPO_NAME = "NetoApps"',
        "def _comparison_version_tuple",
        'expected_digest = _asset_digest(asset)',
    )

    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir).resolve()

    def run(self) -> UIGuardReport:
        errors: list[str] = []
        warnings: list[str] = []
        checks = 0
        app = self.project_dir / "asistan beta.py"
        checks += 1
        if not app.is_file():
            errors.append("Ana arayüz dosyası bulunamadı.")
        else:
            source = app.read_text(encoding="utf-8-sig", errors="replace")
            for marker in self.REQUIRED_MARKERS:
                checks += 1
                if marker not in source:
                    errors.append(f"Arayüz sözleşmesi eksik: {marker}")

        updater = self.project_dir / "neto_updater.py"
        checks += 1
        if not updater.is_file():
            errors.append("Güncelleme motoru bulunamadı.")
        else:
            source = updater.read_text(encoding="utf-8-sig", errors="replace")
            for marker in self.UPDATE_MARKERS:
                checks += 1
                if marker not in source:
                    errors.append(f"Güncelleme sözleşmesi eksik: {marker}")
        helper = self.project_dir / "neto_update_helper.py"
        checks += 1
        if not helper.is_file() or "def _exe_update_script" not in helper.read_text(encoding="utf-8-sig", errors="replace"):
            errors.append("EXE güncelleme yardımcısı eksik: def _exe_update_script")
            if 'APP_VERSION = "1.42.0"' not in (self.project_dir / "neto_version.py").read_text(encoding="utf-8-sig", errors="replace"):
                warnings.append("1.42 sürüm kaynağı güncel değil")

        for log_name in ("terminal_detached.log", "crash.log", "now_playing.log"):
            path = self.project_dir / "logs" / log_name
            if not path.is_file():
                continue
            checks += 1
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-160:]
            for pattern in self.ERROR_PATTERNS:
                if any(re.search(pattern, line) for line in lines):
                    errors.append(f"{log_name}: {pattern}")
            if any("WINDOW_ICON_ERROR" in line for line in lines):
                warnings.append(f"{log_name}: pencere simgesi uyarısı")

        return UIGuardReport(not errors, errors, warnings, checks)


def check_ui(project_dir: str | Path = ".") -> dict[str, object]:
    return NetOpsUIGuardAgent(project_dir).run().as_dict()


__all__ = ["NetOpsUIGuardAgent", "UIGuardReport", "check_ui"]
