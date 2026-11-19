"""Read-only loader for Agent Skills used by the local NetOps agent.

Skills are instruction files, not executable plugins. This module discovers
``SKILL.md`` files, selects the few relevant to a task, and returns bounded
guidance for the local model without executing bundled scripts.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MAX_SKILL_BYTES = 96 * 1024
DEFAULT_LIMIT = 4
DEFAULT_CONTEXT_CHARS = 3200


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    path: Path
    source: str
    instructions: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "source": self.source,
        }


def _skill_roots(project_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("NETOPS_SKILL_DIRS", "")
    if configured:
        roots.extend(Path(item).expanduser() for item in configured.split(os.pathsep) if item.strip())
    if project_dir:
        project = Path(project_dir).expanduser().resolve()
        roots.extend((project / ".agents" / "skills", project / ".codex" / "skills"))
    home = Path.home()
    roots.extend((home / ".codex" / "skills", home / ".agents" / "skills"))

    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def _frontmatter(text: str) -> tuple[str, str, str]:
    header: dict[str, str] = {}
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    if match:
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip().strip("'\"")
            header[key.strip().casefold()] = value
        text = text[match.end():]
    return header.get("name", ""), header.get("description", ""), text


def _read_skill(path: Path, source: str) -> SkillRecord | None:
    try:
        if path.is_symlink() or path.stat().st_size > MAX_SKILL_BYTES:
            return None
        raw = path.read_text(encoding="utf-8", errors="replace")
        name, description, instructions = _frontmatter(raw)
        name = name.strip() or path.parent.name
        description = description.strip() or "Yerel agent çalışma kılavuzu."
        return SkillRecord(name, description, path.resolve(), source, instructions.strip())
    except OSError:
        return None


def discover(project_dir: str | os.PathLike[str] | None = None) -> list[SkillRecord]:
    """Discover skills in project and user locations without executing them."""
    records: list[SkillRecord] = []
    seen_names: set[str] = set()
    for root in _skill_roots(project_dir):
        if not root.is_dir():
            continue
        try:
            paths = sorted(root.rglob("SKILL.md"))
        except OSError:
            continue
        for path in paths:
            record = _read_skill(path, str(root))
            if record is None or record.name.casefold() in seen_names:
                continue
            seen_names.add(record.name.casefold())
            records.append(record)
    return records


_ALIASES = {
    "windows": {"windows", "win", "pc", "bilgisayar", "masaustu", "masaüstü", "pencere"},
    "input": {"mouse", "fare", "klavye", "tıkla", "tikla", "yaz", "ekran", "screenshot"},
    "testing": {"test", "hata", "bug", "çökme", "cokme", "doğrula", "dogrula", "qa"},
    "security": {"güvenlik", "guvenlik", "izin", "açık", "acik", "risk", "saldırı"},
    "coding": {"kod", "python", "düzelt", "duzelt", "ekle", "refactor", "proje"},
}

_SKILL_TRIGGERS = {
    "systematic-debugging": {"hata", "bug", "çökme", "cokme", "çalışmıyor", "calismiyor", "traceback"},
    "test-driven-development": {"test", "tdd", "bug", "düzelt", "duzelt", "özellik", "ozellik"},
    "verification-before-completion": {"doğrula", "dogrula", "test", "tamamlandı", "tamamlandi", "geçti", "gecti"},
    "writing-plans": {"plan", "planla", "planlama", "mimari", "adımlar", "adimlar"},
    "receiving-code-review": {"review", "inceleme", "yorum", "geri bildirim", "pull request", "pr"},
}


def _tokens(value: str) -> set[str]:
    return {item for item in re.findall(r"[\w.-]{3,}", value.casefold()) if item}


def select(task: str, *, project_dir: str | os.PathLike[str] | None = None, limit: int = DEFAULT_LIMIT) -> list[SkillRecord]:
    query = _tokens(str(task or ""))
    scored: list[tuple[int, int, SkillRecord]] = []
    for index, record in enumerate(discover(project_dir)):
        haystack = f"{record.name} {record.description}".casefold()
        score = len(query.intersection(_tokens(haystack))) * 4
        trigger_terms = _SKILL_TRIGGERS.get(record.name.casefold(), set())
        score += len(query.intersection(trigger_terms)) * 5
        for alias_group in _ALIASES.values():
            if query.intersection(alias_group) and any(word in haystack for word in alias_group):
                score += 2
        if score:
            scored.append((score, -index, record))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[: max(1, int(limit))]]


def build_context(
    task: str,
    *,
    project_dir: str | os.PathLike[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    max_chars: int = DEFAULT_CONTEXT_CHARS,
) -> str:
    selected = select(task, project_dir=project_dir, limit=limit)
    if not selected:
        return "Aktif skill bulunamadı; yalnızca NetOps güvenli araç politikası uygulanıyor."
    chunks: list[str] = []
    remaining = max(500, int(max_chars))
    for record in selected:
        header = f"\n--- SKILL: {record.name} ---\n{record.description}\n"
        body = record.instructions[: max(0, remaining - len(header))]
        chunk = header + body + "\n"
        chunks.append(chunk)
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "".join(chunks).strip()


def status(project_dir: str | os.PathLike[str] | None = None) -> dict[str, object]:
    records = discover(project_dir)
    return {
        "count": len(records),
        "skills": [record.as_dict() for record in records],
        "roots": [str(root) for root in _skill_roots(project_dir)],
    }


__all__ = ["SkillRecord", "build_context", "discover", "select", "status"]
