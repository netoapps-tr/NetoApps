"""Non-destructive error detector for NetOps development diagnostics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ErrorFinding:
    severity: str
    source: str
    message: str
    line: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "source": self.source,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class ErrorDetectionReport:
    files_scanned: int = 0
    findings: list[ErrorFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(item.severity == "critical" for item in self.findings)

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "files_scanned": self.files_scanned,
            "error_count": self.error_count,
            "critical_count": self.critical_count,
            "findings": [item.as_dict() for item in self.findings],
        }

    def summary(self) -> str:
        if self.ok:
            return f"Hata Tespit Agent: hata yok ({self.files_scanned} dosya tarandı)."
        critical = self.critical_count
        return (
            f"Hata Tespit Agent: {self.error_count} hata, {critical} kritik hata; "
            f"{self.files_scanned} dosya tarandı."
        )


class NetOpsErrorDetectionAgent:
    """Reads recent logs and reports actionable failures without changing files."""

    LOG_NAMES = ("*.log", "*.txt")
    ERROR_RE = re.compile(
        r"(?i)(traceback|critical|fatal|exception|\berror\b|failed|failure|"
        r"tk_callback_exception|copy_failed|update.*failed)"
    )
    INFO_FALSE_POSITIVES = re.compile(r"(?i)error.?free|no errors?|error_count.?0|without error")

    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir).resolve()

    def _iter_logs(self) -> list[Path]:
        paths: set[Path] = set()
        for folder in (self.project_dir / "logs", self.project_dir):
            if not folder.is_dir():
                continue
            for pattern in self.LOG_NAMES:
                paths.update(item for item in folder.glob(pattern) if item.is_file())
        return sorted(paths)

    def run(self, *, max_lines_per_file: int = 500) -> ErrorDetectionReport:
        report = ErrorDetectionReport()
        for path in self._iter_logs():
            report.files_scanned += 1
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            start = max(0, len(lines) - max(1, int(max_lines_per_file)))
            seen: set[tuple[str, int, str]] = set()
            for number, raw in enumerate(lines[start:], start=start + 1):
                message = raw.strip()
                if (
                    not message
                    or "report_callback_exception installed" in message.casefold()
                    or self.INFO_FALSE_POSITIVES.search(message)
                    or not self.ERROR_RE.search(message)
                ):
                    continue
                # A Tk callback marker already represents the following
                # traceback header; reporting both would inflate the count.
                if message.casefold().startswith("traceback (most recent call last):"):
                    previous = lines[number - 2].strip().casefold() if number >= 2 else ""
                    if "callback_exception" in previous or previous.endswith("exception]"):
                        continue
                lowered = message.casefold()
                severity = "critical" if any(
                    marker in lowered for marker in ("traceback", "critical", "fatal", "exception", "copy_failed")
                ) else "error"
                key = (str(path), number, message[:600])
                if key in seen:
                    continue
                seen.add(key)
                report.findings.append(ErrorFinding(severity, str(path), message[:600], number))
        return report


def detect_errors(project_dir: str | Path = ".") -> dict[str, object]:
    return NetOpsErrorDetectionAgent(project_dir).run().as_dict()


__all__ = ["ErrorFinding", "ErrorDetectionReport", "NetOpsErrorDetectionAgent", "detect_errors"]
