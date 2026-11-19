"""Axvord: NetOps'un sunucusuz yerel agent çekirdeği.

Axvord ürün adını değiştirmez; NetOps içindeki agent çalışma katmanının adıdır.
Skill kılavuzlarını seçer, güvenli cihaz araçlarını çalıştırır ve diğer görevleri
yerel kodlama modeline aktarır. Riskli işlemler köprüdeki izin/onay kapısından
geçmeden yürütülmez.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from neto_agent_bridge import AgentToolBridge
from neto_local_coder import analyze, status as coder_status


AXVORD_NAME = "Axvord"
AXVORD_VERSION = "0.1.0"
AGENT_COMMANDS = frozenset({
    ".agent",
    "agent",
})


def is_activation_command(value: str) -> bool:
    normalized = " ".join(str(value or "").casefold().split())
    return normalized in AGENT_COMMANDS


class AxvordCore:
    """NetOps agent çekirdeğinin tek giriş noktası."""

    name = AXVORD_NAME
    version = AXVORD_VERSION

    def __init__(
        self,
        workspace: str | os.PathLike[str],
        *,
        permission_manager: Any = None,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.tools = AgentToolBridge(self.workspace, permission_manager=permission_manager)

    @classmethod
    def is_activation_command(cls, value: str) -> bool:
        return is_activation_command(value)

    def dispatch(self, task: str, *, approved: bool = False) -> dict[str, Any]:
        return self.tools.dispatch(task, approved=approved)

    def skill_context(self, task: str, *, max_chars: int = 3200) -> str:
        return self.tools.skill_context(task, max_chars=max_chars)

    def analyze(
        self,
        task: str,
        *,
        files: Iterable[str] | None = None,
        timeout: int = 240,
    ) -> str:
        return analyze(
            task,
            project_dir=self.workspace,
            files=files,
            timeout=timeout,
            skill_context=self.skill_context(task),
        )

    def status(self) -> dict[str, object]:
        return {
            # Internal diagnostic identity; never render this value in the UI.
            "core_id": self.name.casefold(),
            "version": self.version,
            "workspace": str(self.workspace),
            "coder": coder_status(self.workspace).as_dict(),
            "skills": self.tools.skill_status(),
        }


__all__ = ["AGENT_COMMANDS", "AXVORD_NAME", "AXVORD_VERSION", "AxvordCore", "is_activation_command"]
