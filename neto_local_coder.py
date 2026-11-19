"""NetOps icin sunucusuz, yerel kodlama modeli baglayicisi.

Bu modul API, Ollama veya Python model paketi kullanmaz. Uygulama paketine
eklenen llama.cpp calistiricisini ve GGUF modelini bulur; ikisi yoksa sadece
durum bilgisi verir ve ana uygulamanin acilmasini engellemez.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MODEL_GLOB = "*coder*.gguf"
PREFERRED_MODELS = (
    "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
    "qwen2.5-coder-3b-instruct-q3_k_m.gguf",
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
)
MAX_CONTEXT_CHARS = 6500


class LocalCoderUnavailable(RuntimeError):
    """Yerel kodlama modeli veya calistirici hazir degil."""


@dataclass(frozen=True)
class LocalCoderStatus:
    ready: bool
    executable: str = ""
    model: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "executable": self.executable,
            "model": self.model,
            "message": self.message,
        }


def _project_root(project_dir: str | os.PathLike[str] | None = None) -> Path:
    return Path(project_dir).expanduser().resolve() if project_dir else Path(__file__).resolve().parent


def find_executable(project_dir: str | os.PathLike[str] | None = None) -> Path | None:
    root = _project_root(project_dir)
    configured = os.environ.get("NETOPS_LLAMA_CLI", "").strip()
    candidates = [
        Path(configured) if configured else None,
        root / "runtime" / "local_ai" / "llama-cli.exe",
        root / "runtime" / "local_ai" / "llama-cli",
        root / "runtime" / "llama-cli.exe",
        root / "runtime" / "llama-cli",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    for name in ("llama-cli.exe", "llama-cli", "llama"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


def find_model(project_dir: str | os.PathLike[str] | None = None) -> Path | None:
    root = _project_root(project_dir)
    configured = os.environ.get("NETOPS_LOCAL_CODE_MODEL", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    model_dir = root / "models"
    if model_dir.is_dir():
        preferred = [model_dir / name for name in PREFERRED_MODELS if (model_dir / name).is_file()]
        preferred.extend(sorted(
            (item for item in model_dir.glob(DEFAULT_MODEL_GLOB) if item not in preferred),
            key=lambda p: ("q4_k_m" not in p.name.casefold(), p.name),
        ))
        candidates.extend(preferred)
        candidates.extend(sorted(model_dir.glob("*.gguf")))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def status(project_dir: str | os.PathLike[str] | None = None) -> LocalCoderStatus:
    executable = find_executable(project_dir)
    model = find_model(project_dir)
    if not executable and not model:
        return LocalCoderStatus(False, message="Yerel çalıştırıcı ve GGUF kod modeli bulunamadı.")
    if not executable:
        return LocalCoderStatus(False, model=str(model), message="llama.cpp çalıştırıcısı bulunamadı.")
    if not model:
        return LocalCoderStatus(False, executable=str(executable), message="GGUF kod modeli bulunamadı.")
    return LocalCoderStatus(True, str(executable), str(model), "Yerel Kod AI hazır.")


def _read_context_files(project_dir: Path, files: Iterable[str] | None = None) -> str:
    selected = list(files or ("neto_error_detection_agent.py", "neto_local_agent_runner.py", "asistan beta.py"))
    chunks: list[str] = []
    remaining = MAX_CONTEXT_CHARS
    for relative in selected:
        path = (project_dir / relative).resolve()
        try:
            path.relative_to(project_dir.resolve())
        except ValueError:
            continue
        if not path.is_file() or path.stat().st_size > 180_000:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text:
            continue
        part = f"\n--- {path.relative_to(project_dir)} ---\n{text[:min(len(text), remaining)]}\n"
        chunks.append(part)
        remaining -= len(part)
        if remaining <= 0:
            break
    return "".join(chunks)


def build_prompt(task: str, context: str, skill_context: str = "") -> str:
    skill_section = str(skill_context or "").strip()
    if skill_section:
        skill_section = (
            "\n\nAKTİF SKILL KILAVUZLARI (yalnızca politika ve öneri; komutları otomatik çalıştırma):\n"
            f"{skill_section[:3200]}"
        )
    return (
        "Sen NetOps projesinin yerel kod inceleme asistanısın. "
        "Yalnızca verilen görev ve kod bağlamını analiz et. Dosya değiştirme, "
        "komut çalıştırma veya ağ erişimi önermeden önce güvenlik riskini belirt. "
        "Bilgisayara etkili işlemler için mevcut NetOps izinlerini ve kullanıcı onayını "
        "gözet; izin atlatma, yükseltme veya gizli işlem önerme. "
        "Yanıtını Türkçe ver ve şu başlıkları kullan: Bulgular, Önerilen düzeltme, "
        "Test planı. Bilgi yoksa uydurma.\n\n"
        f"GÖREV:\n{str(task or '').strip()[:3000]}\n\n"
        f"KOD BAĞLAMI:\n{context[:MAX_CONTEXT_CHARS]}"
        f"{skill_section}"
    )


def _available_memory_mb() -> int | None:
    try:
        import psutil

        return int(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:
        return None


def analyze(
    task: str,
    *,
    project_dir: str | os.PathLike[str] | None = None,
    files: Iterable[str] | None = None,
    timeout: int = 120,
    skill_context: str | None = None,
) -> str:
    root = _project_root(project_dir)
    current = status(root)
    if not current.ready:
        raise LocalCoderUnavailable(current.message)
    available_mb = _available_memory_mb()
    if available_mb is not None and available_mb < 4096:
        raise LocalCoderUnavailable(
            f"Yerel Kod AI bekletildi: kullanılabilir RAM {available_mb} MB; en az 4096 MB gerekli."
        )
    context = _read_context_files(root, files)
    if skill_context is None:
        try:
            from neto_skill_loader import build_context as _build_skill_context

            skill_context = _build_skill_context(task, project_dir=root)
        except Exception:
            skill_context = ""
    prompt = build_prompt(task, context, skill_context or "")
    command = [
        current.executable,
        "-m", current.model,
        "-p", prompt,
        "-n", "700",
        "-c", "4096",
        "-t", "4",
        "-tb", "4",
        "-b", "256",
        "--temp", "0.15",
        "--no-display-prompt",
        "--single-turn",
        "--simple-io",
        "--log-disable",
        "--color", "off",
    ]
    completed = subprocess.run(
        command,
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(20, min(int(timeout), 300)),
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = (completed.stdout or "").strip()
    # llama-cli prints a small interactive header even in single-turn mode.
    # Keep only the generated answer for the NetOps panel.
    if prompt in output:
        output = output.split(prompt, 1)[1]
    else:
        # Bazı Qwen chat şablonları prompt'u küçük biçim farklarıyla yankılar.
        # Modelin gerçek cevabını beklenen başlıktan itibaren göster.
        for marker in ("\n### Bulgular", "\nBulgular", "\n**Bulgular"):
            marker_index = output.find(marker)
            if marker_index >= 0:
                output = output[marker_index + 1:]
                break
    if "\n> " in output:
        output = output.rsplit("\n> ", 1)[-1]
    if "\n[ Prompt:" in output:
        output = output.split("\n[ Prompt:", 1)[0]
    if output.endswith("\nExiting..."):
        output = output[: -len("\nExiting...")]
    output = output.strip()
    if completed.returncode != 0:
        detail = (completed.stderr or output or "Yerel model hata verdi.").strip()
        raise RuntimeError(detail[-2000:])
    if output.casefold().startswith("error:") or "exceeds the available context size" in output.casefold():
        raise RuntimeError(output[-2000:])
    if not output:
        raise RuntimeError("Yerel model boş cevap verdi.")
    return output


__all__ = [
    "LocalCoderStatus",
    "LocalCoderUnavailable",
    "analyze",
    "find_executable",
    "find_model",
    "status",
]
