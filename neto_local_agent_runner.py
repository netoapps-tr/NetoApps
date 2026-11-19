"""Sunucusuz, çalışma-alanı sınırlı NetOps kod ajanı.

Bu modül bir model sağlayıcısı değildir. Yerel veya uzaktaki bir modelden gelen
planı güvenli biçimde uygulamak için cihazda çalışan yürütme katmanıdır. Böylece
aynı NetOps kurulumu Windows, macOS veya Linux'ta merkezi bir NetOps sunucusuna
bağlanmadan proje inceleme ve doğrulama yapabilir.
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


RUNNER_VERSION = "1.41.0"
MAX_FILE_BYTES = 512 * 1024
MAX_WRITE_BYTES = 256 * 1024
MAX_SEARCH_RESULTS = 80
SKIPPED_DIRECTORIES = {
    ".git", ".netops", ".netops-agent", "__pycache__", ".pytest_cache",
    ".mypy_cache", "build", "dist", "node_modules", "venv", ".venv",
}
RISKY_CAPABILITIES = frozenset({"file_write", "file_delete", "network", "package_install"})
SAFE_CAPABILITIES = frozenset({"project_read", "project_search", "verify"})
TEXT_FILE_EXTENSIONS = frozenset({
    "", ".cfg", ".c", ".cpp", ".css", ".csv", ".h", ".html", ".ini",
    ".js", ".json", ".log", ".md", ".ps1", ".py", ".sh", ".toml", ".ts",
    ".txt", ".yaml", ".yml",
})
WINDOWS_RESERVED_NAMES = frozenset({
    "AUX", "CON", "NUL", "PRN", "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
})


class AgentRunnerError(RuntimeError):
    """Yerel agent çalışma alanı hatası."""


class WorkspaceBoundaryError(AgentRunnerError):
    """Agent'ın seçili çalışma alanının dışına çıkması engellendi."""


class ApprovalRequired(AgentRunnerError):
    """Riskli bir araç çağrısı görünür kullanıcı onayı bekliyor."""


@dataclass(frozen=True)
class AgentStep:
    id: str
    title: str
    capability: str
    automatic: bool
    detail: str


@dataclass(frozen=True)
class AgentPlan:
    task_id: str
    prompt: str
    intent: str
    steps: tuple[AgentStep, ...]
    requires_approval: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    task_id: str
    workspace: str
    started_at: float
    finished_at: float
    results: tuple[ToolResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)


def default_device_state_dir() -> Path:
    """Kayıtları proje yerine yalnızca cihazda tutar."""
    override = os.environ.get("NETOPS_AGENT_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "NetoAssistant" / "local_agent"
    return Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "netops" / "local_agent"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").casefold()).strip(".-")
    return cleaned[:80] or "workspace"


class NetOpsLocalAgentRunner:
    """Sunucusuz proje ajanının sınırlı ve denetlenebilir araç seti."""

    def __init__(self, workspace: str | os.PathLike[str], *, state_dir: str | os.PathLike[str] | None = None) -> None:
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise AgentRunnerError(f"Çalışma alanı bulunamadı: {root}")
        self.workspace = root
        self.state_dir = Path(state_dir).expanduser().resolve() if state_dir else default_device_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.state_dir / f"{_safe_name(root.name)}-history.json"

    def device_info(self) -> dict[str, str]:
        return {
            "runner_version": RUNNER_VERSION,
            "mode": "local-only",
            "platform": platform.system() or "unknown",
            "python": platform.python_version(),
            "workspace": str(self.workspace),
        }

    def plan(self, prompt: str) -> AgentPlan:
        text = " ".join(str(prompt or "").split())
        if not text:
            raise AgentRunnerError("Agent görevi boş olamaz.")
        lowered = text.casefold()
        steps: list[AgentStep] = [
            AgentStep("inspect", "Projeyi tara", "project_read", True, "Dosya yapısı ve temel proje bilgisi okunacak."),
        ]
        intent = "inspect"
        approvals: list[str] = []

        if any(word in lowered for word in ("hata", "çalışmıyor", "bozuk", "test", "bug", "traceback")):
            intent = "diagnose"
            steps.extend((
                AgentStep("search", "İlgili kodu ara", "project_search", True, "Hata ve görev anahtarları çalışma alanında aranacak."),
                AgentStep("verify", "Güvenli doğrulama çalıştır", "verify", True, "Python derleme ve mevcut testler kabuksuz çalıştırılacak."),
            ))
        elif any(word in lowered for word in ("incele", "özetle", "analiz", "review", "açık")):
            intent = "review"
            steps.append(AgentStep("search", "İlgili kodu ara", "project_search", True, "Görevle eşleşen kaynak dosyalar aranacak."))
        elif any(word in lowered for word in ("yaz", "ekle", "değiştir", "düzelt", "uygula", "refactor")):
            intent = "change_request"
            steps.extend((
                AgentStep("search", "Değişecek alanı bul", "project_search", True, "Etkilenecek kaynaklar önce okunacak."),
                AgentStep("propose", "Patch planı hazırla", "file_write", False, "Dosya değişiklikleri uygulanmadan önce onaya sunulacak."),
                AgentStep("verify", "Değişiklik sonrası doğrula", "verify", False, "Onaylı patch sonrası test/derleme çalışacak."),
            ))
            approvals.append("file_write")

        return AgentPlan(
            task_id=uuid.uuid4().hex,
            prompt=text,
            intent=intent,
            steps=tuple(steps),
            requires_approval=tuple(approvals),
        )

    def run_safe_steps(self, plan: AgentPlan) -> AgentRun:
        """Sadece okuma, arama ve doğrulama adımlarını cihazda yürütür."""
        started = time.time()
        results: list[ToolResult] = []
        for step in plan.steps:
            if not step.automatic:
                results.append(ToolResult(step.id, True, "Bu adım kullanıcı onayı bekliyor.", {"approval": step.capability}))
                continue
            try:
                if step.id == "inspect":
                    results.append(self.inspect_project())
                elif step.id == "search":
                    results.append(self.search(plan.prompt))
                elif step.id == "verify":
                    results.append(self.verify())
            except Exception as exc:
                results.append(ToolResult(step.id, False, str(exc)))
        finished = time.time()
        run = AgentRun(uuid.uuid4().hex, plan.task_id, str(self.workspace), started, finished, tuple(results))
        self._append_history(plan, run)
        return run

    def inspect_project(self) -> ToolResult:
        files = 0
        python_files = 0
        for path in self._iter_files():
            files += 1
            if path.suffix.casefold() == ".py":
                python_files += 1
        return ToolResult(
            "inspect",
            True,
            "Çalışma alanı yerelde tarandı.",
            {"files": files, "python_files": python_files, "device": self.device_info()},
        )

    def read_file(self, relative_path: str | os.PathLike[str]) -> str:
        path = self._resolve_workspace_path(relative_path)
        if not path.is_file():
            raise AgentRunnerError(f"Dosya bulunamadı: {relative_path}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise AgentRunnerError(f"Dosya güvenli okuma sınırını aşıyor: {relative_path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def create_text_file(
        self,
        relative_path: str | os.PathLike[str],
        content: str,
        *,
        approved: bool = False,
        overwrite: bool = False,
    ) -> ToolResult:
        """Create a bounded UTF-8 text file after explicit user approval.

        The path is always resolved below the selected workspace. Existing files
        are preserved unless the caller explicitly opts into overwrite.
        """
        self.require_approval("file_write", approved=approved)
        path = self._resolve_workspace_path(relative_path)
        if path == self.workspace:
            raise AgentRunnerError("Dosya yolu bir dosya adı içermeli.")
        if path.suffix.casefold() not in TEXT_FILE_EXTENSIONS:
            raise AgentRunnerError("Yalnızca güvenli metin dosyaları oluşturulabilir.")
        if path.name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
            raise AgentRunnerError("Windows tarafından ayrılmış dosya adı kullanılamaz.")
        if path.exists() and not path.is_file():
            raise AgentRunnerError("Hedef yol bir klasör; dosya oluşturulamaz.")
        if path.exists() and not overwrite:
            raise AgentRunnerError("Dosya zaten var; üzerine yazmak için açıkça overwrite=True verilmeli.")

        text = str(content)
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            raise AgentRunnerError(f"Dosya güvenli yazma sınırını aşıyor: {MAX_WRITE_BYTES} bayt.")

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, path)
        finally:
            try:
                if temporary.exists():
                    temporary.unlink()
            except OSError:
                pass
        return ToolResult(
            "file_write",
            True,
            "Metin dosyası oluşturuldu.",
            {"path": str(path.relative_to(self.workspace)), "bytes": len(encoded), "overwritten": bool(overwrite)},
        )

    def create_text_file_from_command(self, command: str, *, approved: bool = False) -> ToolResult:
        """Create a text file from an explicit Turkish chat command."""
        match = re.search(
            r"(?:dosya\s+(?:oluştur|olustur|yaz)|not\s+kaydet|metin\s+belgesi\s+aç|metin\s+belgesi\s+ac)"
            r"(?:\s+([^\s:]+))?"
            r"(?:\s+(?:içerik|icerik|metin)\s*[:=]\s*(.*))?$",
            str(command or "").strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            raise AgentRunnerError("Komut biçimi: dosya oluştur not.md içerik: metin")
        filename = str(match.group(1) or "netops-notu.txt").strip()
        if "." not in Path(filename).name:
            filename = f"{filename}.txt"
        content = match.group(2)
        if content is None:
            content = "NetOps Notu\n"
        return self.create_text_file(filename, content, approved=approved)

    def search(self, query: str, *, limit: int = MAX_SEARCH_RESULTS) -> ToolResult:
        terms = [term for term in re.findall(r"[\w.-]{3,}", str(query).casefold()) if term not in {"netops", "agent", "görev", "gorev"}]
        if not terms:
            terms = [str(query).strip().casefold()]
        matches: list[dict[str, Any]] = []
        for path in self._iter_files():
            if len(matches) >= min(max(1, int(limit)), MAX_SEARCH_RESULTS):
                break
            if path.stat().st_size > MAX_FILE_BYTES or path.suffix.casefold() not in {".py", ".json", ".md", ".txt", ".ps1", ".yml", ".yaml"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                normalized = line.casefold()
                if any(term and term in normalized for term in terms):
                    matches.append({"path": str(path.relative_to(self.workspace)), "line": number, "text": line[:240]})
                    if len(matches) >= min(max(1, int(limit)), MAX_SEARCH_RESULTS):
                        break
        return ToolResult("search", True, f"Yerel arama {len(matches)} eşleşme buldu.", {"matches": matches})

    def verify(self, targets: Iterable[str | os.PathLike[str]] | None = None, *, timeout: int = 45) -> ToolResult:
        """Kabuk açmadan güvenli Python derleme/doğrulama çalıştırır."""
        chosen = list(targets or self._default_verify_targets())
        if not chosen:
            return ToolResult("verify", True, "Derlenecek Python dosyası bulunamadı.", {"command": []})
        absolute = [str(self._resolve_workspace_path(item)) for item in chosen]
        command = [sys.executable, "-m", "py_compile", *absolute]
        completed = subprocess.run(
            command,
            cwd=str(self.workspace),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, min(int(timeout), 120)),
            check=False,
        )
        data = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "targets": [str(Path(path).relative_to(self.workspace)) for path in absolute],
        }
        return ToolResult("verify", completed.returncode == 0, "Python doğrulaması tamamlandı." if completed.returncode == 0 else "Python doğrulaması hata verdi.", data)

    def require_approval(self, capability: str, *, approved: bool = False) -> None:
        if capability in RISKY_CAPABILITIES and not approved:
            raise ApprovalRequired(f"'{capability}' için görünür kullanıcı onayı gerekiyor.")

    def _default_verify_targets(self) -> list[str]:
        preferred = ["asistan beta.py", "neto_ai.py", "netops_harbilig_engine.py"]
        selected = [name for name in preferred if (self.workspace / name).is_file()]
        if selected:
            return selected
        return [
            str(path.relative_to(self.workspace))
            for path in self._iter_files()
            if path.suffix.casefold() == ".py"
        ][:5]

    def _resolve_workspace_path(self, relative_path: str | os.PathLike[str]) -> Path:
        candidate = Path(relative_path)
        path = candidate.resolve() if candidate.is_absolute() else (self.workspace / candidate).resolve()
        if not _is_relative_to(path, self.workspace):
            raise WorkspaceBoundaryError("Agent çalışma alanı dışındaki dosyaya erişemez.")
        return path

    def _iter_files(self):
        for path in self.workspace.rglob("*"):
            if any(part.casefold() in SKIPPED_DIRECTORIES for part in path.relative_to(self.workspace).parts):
                continue
            if path.is_file():
                yield path

    def _append_history(self, plan: AgentPlan, run: AgentRun) -> None:
        try:
            previous: list[dict[str, Any]] = []
            if self.history_path.is_file():
                value = json.loads(self.history_path.read_text(encoding="utf-8"))
                if isinstance(value, list):
                    previous = value[-49:]
            previous.append({"plan": asdict(plan), "run": asdict(run)})
            temporary = self.history_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.history_path)
        except Exception:
            # Geçmiş yazılamasa da ajan güvenli araç sonuçlarını kullanıcıya döndürür.
            pass


def main(argv: list[str] | None = None) -> int:
    """Basit, sunucusuz komut satırı giriş noktası: `python -m neto_local_agent_runner`."""
    import argparse

    parser = argparse.ArgumentParser(description="NetOps yerel Agent Runner")
    parser.add_argument("workspace", help="Ajanın erişebileceği proje klasörü")
    parser.add_argument("task", help="Doğal dil görev açıklaması")
    parser.add_argument("--run-safe", action="store_true", help="Sadece güvenli okuma/arama/doğrulama adımlarını çalıştır")
    args = parser.parse_args(argv)
    runner = NetOpsLocalAgentRunner(args.workspace)
    plan = runner.plan(args.task)
    payload: dict[str, Any] = {"device": runner.device_info(), "plan": asdict(plan)}
    if args.run_safe:
        payload["run"] = asdict(runner.run_safe_steps(plan))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def create_local_agent_panel(parent, *, root, workspace: str | os.PathLike[str], palette: dict[str, str], initial_task: str = ""):
    """CustomTkinter için yerel Agent Runner ekranı.

    Ağ isteği yapmaz. Ağ/model bağlayıcıları bu panelin dışında, ayrı ve
    kullanıcının seçtiği sağlayıcı izinleriyle eklenir.
    """
    import threading
    import tkinter as tk
    from tkinter import filedialog

    import customtkinter as ctk

    colors = {
        "bg": palette.get("bg", "#0B0B0F"),
        "card": palette.get("card", "#19191F"),
        "entry": palette.get("entry_bg", "#101015"),
        "border": palette.get("entry_border", "#35353F"),
        "text": palette.get("text_main", "#F4F4F5"),
        "muted": palette.get("text_dim", "#A1A1AA"),
        "accent": palette.get("neon", "#3B82F6"),
        "hover": palette.get("button_hover", "#292932"),
    }
    panel = ctk.CTkFrame(parent, fg_color=colors["bg"], corner_radius=0)
    panel.pack(fill="both", expand=True)
    state = {"workspace": Path(workspace).resolve(), "plan": None, "running": False}

    header = ctk.CTkFrame(panel, fg_color=colors["card"], corner_radius=16)
    header.pack(fill="x", padx=20, pady=(20, 10))
    title_box = ctk.CTkFrame(header, fg_color="transparent")
    title_box.pack(side="left", fill="x", expand=True, padx=18, pady=15)
    ctk.CTkLabel(title_box, text="NetOps Agent Runner", anchor="w", font=("Segoe UI Semibold", 22), text_color=colors["text"]).pack(fill="x")
    status = ctk.CTkLabel(title_box, text="Bu cihazda yerel çalışır · Sunucu bağlantısı yok", anchor="w", font=("Segoe UI", 11), text_color=colors["muted"])
    status.pack(fill="x", pady=(3, 0))

    workspace_card = ctk.CTkFrame(panel, fg_color=colors["card"], corner_radius=16)
    workspace_card.pack(fill="x", padx=20, pady=(0, 10))
    workspace_label = ctk.CTkLabel(workspace_card, text="", anchor="w", font=("Consolas", 11), text_color=colors["muted"])
    workspace_label.pack(side="left", fill="x", expand=True, padx=16, pady=12)

    task_card = ctk.CTkFrame(panel, fg_color=colors["card"], corner_radius=16)
    task_card.pack(fill="x", padx=20, pady=(0, 10))
    task_entry = ctk.CTkTextbox(task_card, height=92, fg_color=colors["entry"], border_width=1, border_color=colors["border"], text_color=colors["text"], corner_radius=12, font=("Segoe UI", 12))
    task_entry.pack(fill="x", padx=14, pady=(14, 8))
    task_entry.insert("1.0", str(initial_task or "Bu projedeki hataları bul, güvenli testleri çalıştır ve raporla."))
    actions = ctk.CTkFrame(task_card, fg_color="transparent")
    actions.pack(fill="x", padx=14, pady=(0, 14))

    output = ctk.CTkTextbox(panel, fg_color=colors["entry"], border_width=1, border_color=colors["border"], text_color=colors["text"], corner_radius=16, font=("Consolas", 11))
    output.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    output.configure(state="disabled")

    def write_output(value: Any) -> None:
        try:
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.insert("1.0", text)
            output.configure(state="disabled")
        except Exception:
            pass

    def update_workspace_label() -> None:
        workspace_label.configure(text=f"Çalışma alanı: {state['workspace']}")

    def choose_workspace() -> None:
        selected = filedialog.askdirectory(parent=root, initialdir=str(state["workspace"]), title="Agent çalışma alanını seç")
        if selected:
            state["workspace"] = Path(selected).resolve()
            state["plan"] = None
            update_workspace_label()
            status.configure(text="Çalışma alanı değişti · yeni görev planı bekleniyor")

    def create_file() -> None:
        """Open an explicit approval dialog before writing a workspace text file."""
        if state["running"]:
            return
        selected = filedialog.asksaveasfilename(
            parent=root,
            initialdir=str(state["workspace"]),
            title="NetOps çalışma alanında dosya oluştur",
            defaultextension=".md",
            filetypes=[
                ("Metin dosyaları", "*.md *.txt *.json *.py *.ps1 *.yaml *.yml"),
                ("Tüm dosyalar", "*.*"),
            ],
        )
        if not selected:
            return

        dialog = ctk.CTkToplevel(root)
        dialog.title("Dosya oluşturma onayı")
        dialog.geometry("620x430")
        dialog.transient(root)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text=f"Hedef: {selected}\nBu işlem yalnızca seçili çalışma alanında ve açık onayla yapılır.",
            anchor="w",
            justify="left",
            text_color=colors["muted"],
        ).pack(fill="x", padx=18, pady=(18, 8))
        editor = ctk.CTkTextbox(
            dialog,
            fg_color=colors["entry"],
            border_width=1,
            border_color=colors["border"],
            text_color=colors["text"],
            corner_radius=12,
            font=("Consolas", 11),
        )
        editor.pack(fill="both", expand=True, padx=18, pady=8)
        overwrite = tk.BooleanVar(dialog, value=False)
        ctk.CTkCheckBox(
            dialog,
            text="Varsa üzerine yaz (ayrıca onaylanır)",
            variable=overwrite,
            text_color=colors["muted"],
        ).pack(anchor="w", padx=18, pady=(0, 8))
        dialog_actions = ctk.CTkFrame(dialog, fg_color="transparent")
        dialog_actions.pack(fill="x", padx=18, pady=(0, 16))

        def confirm_file_write() -> None:
            try:
                relative = Path(selected).resolve().relative_to(state["workspace"])
            except ValueError:
                status.configure(text="Dosya oluşturma engellendi · çalışma alanı dışı yol")
                dialog.destroy()
                return
            content = editor.get("1.0", "end-1c")
            allow_overwrite = bool(overwrite.get())
            dialog.destroy()
            state["running"] = True
            file_button.configure(state="disabled")
            status.configure(text="Dosya onaylı biçimde oluşturuluyor…")

            def worker() -> None:
                try:
                    result = NetOpsLocalAgentRunner(state["workspace"]).create_text_file(
                        relative,
                        content,
                        approved=True,
                        overwrite=allow_overwrite,
                    )
                    payload = {"file": asdict(result)}
                    message = result.message
                except Exception as exc:
                    payload = {"error": str(exc)}
                    message = f"Dosya oluşturulamadı: {exc}"

                def finish() -> None:
                    if not panel.winfo_exists():
                        return
                    state["running"] = False
                    file_button.configure(state="normal")
                    status.configure(text=message)
                    write_output(payload)

                root.after(0, finish)

            threading.Thread(target=worker, daemon=True, name="NetOpsSafeFileWriter").start()

        ctk.CTkButton(
            dialog_actions,
            text="İptal",
            width=100,
            command=dialog.destroy,
            fg_color=colors["entry"],
            hover_color=colors["hover"],
        ).pack(side="right")
        ctk.CTkButton(
            dialog_actions,
            text="Onayla ve oluştur",
            width=170,
            command=confirm_file_write,
            fg_color=colors["accent"],
            hover_color=colors["hover"],
        ).pack(side="right", padx=(0, 8))

    def build_plan() -> AgentPlan | None:
        task = task_entry.get("1.0", "end").strip()
        try:
            runner = NetOpsLocalAgentRunner(state["workspace"])
            plan = runner.plan(task)
            state["plan"] = plan
            write_output({"device": runner.device_info(), "plan": asdict(plan)})
            waiting = ", ".join(plan.requires_approval) or "yok"
            status.configure(text=f"Plan hazır · onay bekleyen izin: {waiting}")
            return plan
        except Exception as exc:
            status.configure(text=f"Plan oluşturulamadı: {exc}")
            write_output({"error": str(exc)})
            return None

    def run_safe() -> None:
        if state["running"]:
            return
        plan = state.get("plan") or build_plan()
        if plan is None:
            return
        state["running"] = True
        run_button.configure(state="disabled")
        status.configure(text="Güvenli adımlar yerelde çalışıyor…")

        def worker() -> None:
            try:
                result = NetOpsLocalAgentRunner(state["workspace"]).run_safe_steps(plan)
                payload = {"run": asdict(result), "ok": result.ok}
                message = "Güvenli adımlar tamamlandı." if result.ok else "Bazı güvenli adımlar hata verdi."
            except Exception as exc:
                payload = {"error": str(exc)}
                message = f"Agent çalıştırılamadı: {exc}"

            def finish() -> None:
                if not panel.winfo_exists():
                    return
                state["running"] = False
                run_button.configure(state="normal")
                status.configure(text=message)
                write_output(payload)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="NetOpsLocalAgentRun").start()

    def run_local_ai() -> None:
        if state["running"]:
            return
        task = task_entry.get("1.0", "end").strip()
        if not task:
            status.configure(text="Önce bir görev yaz.")
            return
        state["running"] = True
        ai_button.configure(state="disabled")
        status.configure(text="Yerel Kod AI analiz ediyor…")

        def worker() -> None:
            try:
                from neto_local_coder import analyze, status as coder_status

                result = analyze(task, project_dir=state["workspace"])
                payload = {"model": coder_status(state["workspace"]).as_dict(), "analysis": result}
                message = "Yerel Kod AI analizi tamamlandı."
            except Exception as exc:
                payload = {"error": str(exc)}
                message = f"Yerel Kod AI hazır değil veya hata verdi: {exc}"

            def finish() -> None:
                if not panel.winfo_exists():
                    return
                state["running"] = False
                ai_button.configure(state="normal")
                status.configure(text=message)
                write_output(payload)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="NetOpsLocalCoderAnalysis").start()

    ctk.CTkButton(workspace_card, text="Klasör Seç", width=112, height=34, corner_radius=10, fg_color=colors["entry"], hover_color=colors["hover"], text_color=colors["text"], command=choose_workspace).pack(side="right", padx=12, pady=10)
    ctk.CTkButton(actions, text="Planla", width=110, height=36, corner_radius=10, fg_color=colors["entry"], hover_color=colors["hover"], text_color=colors["text"], command=build_plan).pack(side="left")
    file_button = ctk.CTkButton(actions, text="Dosya Oluştur", width=128, height=36, corner_radius=10, fg_color=colors["entry"], hover_color=colors["hover"], text_color=colors["text"], command=create_file)
    file_button.pack(side="left", padx=(8, 0))
    run_button = ctk.CTkButton(actions, text="Güvenli Adımları Çalıştır", height=36, corner_radius=10, fg_color=colors["accent"], hover_color=colors["hover"], text_color="#FFFFFF", command=run_safe)
    run_button.pack(side="left", padx=(8, 0))
    ai_button = ctk.CTkButton(actions, text="Yerel Kod AI Analiz Et", height=36, corner_radius=10, fg_color="#1E293B", hover_color=colors["hover"], text_color=colors["text"], command=run_local_ai)
    ai_button.pack(side="left", padx=(8, 0))
    ctk.CTkLabel(actions, text="Yazma, silme, paket ve ağ adımları onay olmadan çalışmaz.", text_color=colors["muted"], font=("Segoe UI", 10)).pack(side="right")
    update_workspace_label()
    return panel


if __name__ == "__main__":
    raise SystemExit(main())
