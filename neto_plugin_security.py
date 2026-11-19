"""Static safety checks for NetOps ``.nops`` extensions.

The scanner deliberately does not import or execute plugin code.  It is a
first-pass guard, not a replacement for OS sandboxing or user approval.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PluginFinding:
    severity: str
    code: str
    message: str
    path: str = ""
    line: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
        }


@dataclass
class PluginScanReport:
    plugin_id: str
    findings: list[PluginFinding] = field(default_factory=list)

    @property
    def safe_to_review(self) -> bool:
        return not any(item.severity == "critical" for item in self.findings)

    @property
    def error_count(self) -> int:
        return len(self.findings)

    def as_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "safe_to_review": self.safe_to_review,
            "error_count": self.error_count,
            "findings": [item.as_dict() for item in self.findings],
        }


_DANGEROUS_IMPORTS = {
    "ctypes": ("high", "PLUGIN_NATIVE_API", "Yerel/native API erişimi"),
    "win32api": ("high", "PLUGIN_WINDOWS_API", "Windows API erişimi"),
    "win32con": ("high", "PLUGIN_WINDOWS_API", "Windows API erişimi"),
    "subprocess": ("critical", "PLUGIN_PROCESS", "Harici işlem başlatma"),
    "os": ("high", "PLUGIN_OS", "İşletim sistemi API erişimi"),
    "shutil": ("high", "PLUGIN_FILESYSTEM", "Dosya sistemi işlemleri"),
    "socket": ("high", "PLUGIN_NETWORK", "Ağ soketi erişimi"),
    "requests": ("medium", "PLUGIN_NETWORK", "Ağ isteği"),
    "urllib": ("medium", "PLUGIN_NETWORK", "Ağ isteği"),
}
_DANGEROUS_CALLS = {
    "eval": ("critical", "PLUGIN_DYNAMIC_CODE", "Dinamik kod çalıştırma"),
    "exec": ("critical", "PLUGIN_DYNAMIC_CODE", "Dinamik kod çalıştırma"),
    "compile": ("critical", "PLUGIN_DYNAMIC_CODE", "Dinamik kod derleme"),
    "system": ("critical", "PLUGIN_PROCESS", "Kabuk komutu çalıştırma"),
    "popen": ("critical", "PLUGIN_PROCESS", "Harici işlem çalıştırma"),
    "run": ("high", "PLUGIN_PROCESS", "Harici işlem çağrısı"),
    "Popen": ("critical", "PLUGIN_PROCESS", "Harici işlem çalıştırma"),
    "remove": ("high", "PLUGIN_DELETE", "Dosya silme çağrısı"),
    "unlink": ("high", "PLUGIN_DELETE", "Dosya silme çağrısı"),
    "rmtree": ("critical", "PLUGIN_DELETE", "Klasör silme çağrısı"),
}


def _finding_for_call(node: ast.Call, path: Path) -> PluginFinding | None:
    name = node.func.id if isinstance(node.func, ast.Name) else (
        node.func.attr if isinstance(node.func, ast.Attribute) else ""
    )
    item = _DANGEROUS_CALLS.get(name)
    if item is None:
        return None
    severity, code, message = item
    return PluginFinding(severity, code, message, str(path), node.lineno)


def _scan_python(path: Path) -> list[PluginFinding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [PluginFinding("high", "PLUGIN_SYNTAX", f"Python sözdizimi hatası: {exc.msg}", str(path), exc.lineno)]
    except OSError as exc:
        return [PluginFinding("high", "PLUGIN_READ", f"Dosya okunamadı: {exc}", str(path))]

    findings: list[PluginFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [str(node.module or "").split(".", 1)[0]]
        else:
            call_finding = _finding_for_call(node, path) if isinstance(node, ast.Call) else None
            if call_finding:
                findings.append(call_finding)
            continue
        for name in names:
            item = _DANGEROUS_IMPORTS.get(name)
            if item:
                severity, code, message = item
                findings.append(PluginFinding(severity, code, message, str(path), node.lineno))
    return findings


def scan_plugin(plugin_id: str, root: str | Path, *, files: Iterable[Path] | None = None) -> PluginScanReport:
    """Scan supported source files without importing or running them."""
    base = Path(root).resolve()
    candidates = list(files) if files is not None else [
        path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in {".py", ".lua"}
    ]
    findings: list[PluginFinding] = []
    for path in candidates:
        if path.suffix.lower() == ".py":
            findings.extend(_scan_python(path))
        elif path.suffix.lower() == ".lua":
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                findings.append(PluginFinding("high", "PLUGIN_READ", f"Dosya okunamadı: {exc}", str(path)))
                continue
            if any(token in text for token in ("os.execute", "io.popen", "loadstring")):
                findings.append(PluginFinding("critical", "PLUGIN_LUA_UNSAFE", "Riskli Lua çağrısı bulundu", str(path)))
    return PluginScanReport(plugin_id, findings)


__all__ = ["PluginFinding", "PluginScanReport", "scan_plugin"]
