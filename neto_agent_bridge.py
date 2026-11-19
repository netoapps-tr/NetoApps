"""NetOps yerel agent ile kurulu skill ve cihaz araçları arasındaki güvenli köprü.

Skill dosyaları yalnızca talimat olarak okunur; içlerindeki komutlar çalıştırılmaz.
Okuma, sistem durumu ve Python doğrulaması güvenli araçlardır. Program açma ve
klavye/fare gibi bilgisayarı etkileyen işlemler görünür onay olmadan yürütülmez.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from neto_local_agent_runner import NetOpsLocalAgentRunner
from neto_skill_loader import build_context, status as skill_status


class AgentToolBridge:
    """Yerel agent için sınırlı, denetlenebilir araç katmanı."""

    SAFE_INTENTS = ("system_status", "process_list", "verify")
    INPUT_WORDS = ("tıkla", "tikla", "fare", "mouse", "klavye", "ekrana yaz", "tuşa bas")
    OPEN_WORDS = ("uygulama aç", "program aç", "notepad aç", "chrome aç", "tarayıcı aç")
    FILE_WRITE_WORDS = ("dosya oluştur", "dosya olustur", "dosya yaz", "not kaydet")
    ERROR_SCAN_WORDS = ("hata sayısı", "hata sayisi", "kritik hata", "hataları bul", "hatalari bul", "logları tara", "loglari tara")
    UI_SCAN_WORDS = ("arayüzü denetle", "arayuzu denetle", "arayüz kontrolü", "arayuz kontrolu", "ui kontrol")
    PDF_WORDS = ("pdf oluştur", "pdf olustur", "raporu pdf yap", "raporu pdf'e çevir", "raporu pdf'e cevir")

    def __init__(self, workspace: str | os.PathLike[str], *, permission_manager: Any = None) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.runner = NetOpsLocalAgentRunner(self.workspace)
        self.permission_manager = permission_manager

    def skill_context(self, task: str, *, max_chars: int = 3200) -> str:
        return build_context(task, project_dir=self.workspace, max_chars=max_chars)

    def skill_status(self) -> dict[str, object]:
        return skill_status(self.workspace)

    def system_status(self) -> dict[str, Any]:
        try:
            import psutil

            memory = psutil.virtual_memory()
            return {
                "platform": platform.platform(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_percent": memory.percent,
                "ram_available_mb": int(memory.available / (1024 * 1024)),
            }
        except Exception as exc:
            return {"platform": platform.platform(), "message": f"Sistem durumu sınırlı okunabildi: {exc}"}

    def process_list(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            import psutil

            items = []
            for process in psutil.process_iter(("pid", "name", "memory_percent")):
                try:
                    info = process.info
                    items.append({
                        "pid": int(info.get("pid") or 0),
                        "name": str(info.get("name") or "unknown")[:80],
                        "memory_percent": round(float(info.get("memory_percent") or 0), 2),
                    })
                except (psutil.Error, OSError, ValueError):
                    continue
            return sorted(items, key=lambda item: item["memory_percent"], reverse=True)[: max(1, min(int(limit), 50))]
        except Exception:
            return []

    def _permission_allowed(self, permission: str, context: str) -> bool:
        manager = self.permission_manager
        if manager is None:
            return False
        try:
            return bool(manager.require(permission, context=context))
        except Exception:
            return False

    def open_program(self, target: str, *, approved: bool = False) -> dict[str, Any]:
        """Only opens a small allowlist after explicit approval and permission."""
        normalized = str(target or "").casefold()
        allowlist = {
            "notepad": "notepad.exe",
            "notepad.exe": "notepad.exe",
            "hesap makinesi": "calc.exe",
            "calculator": "calc.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
        }
        executable = next((value for key, value in allowlist.items() if key in normalized), None)
        if not executable:
            return {"ok": False, "approval_required": False, "message": "Bu uygulama güvenli açma listesinde değil."}
        if not approved:
            return {"ok": False, "approval_required": True, "message": f"'{executable}' açılacak. Kullanıcı onayı gerekiyor."}
        if not self._permission_allowed("program_open", f"Agent program açma: {executable}"):
            return {"ok": False, "approval_required": True, "message": "program_open izni verilmedi."}
        try:
            subprocess.Popen([executable], shell=False)
            return {"ok": True, "message": f"{executable} açıldı."}
        except OSError as exc:
            return {"ok": False, "message": f"Program açılamadı: {exc}"}

    def create_file(self, task: str, *, approved: bool = False) -> dict[str, Any]:
        if not approved:
            return {
                "ok": False,
                "approval_required": True,
                "message": "Dosya çalışma alanında oluşturulacak. Onaylamak için 'evet', iptal etmek için 'hayır' yaz.",
            }
        try:
            result = self.runner.create_text_file_from_command(task, approved=True)
            return {"ok": result.ok, "approval_required": False, "message": result.message, "data": result.data}
        except Exception as exc:
            return {"ok": False, "approval_required": False, "message": f"Dosya oluşturulamadı: {exc}"}

    def create_pdf_report(self, *, approved: bool = False) -> dict[str, Any]:
        if not approved:
            return {
                "ok": False,
                "approval_required": True,
                "message": "NetOps teknik raporu masaüstüne PDF olarak yazılacak. Onaylamak için 'evet' yaz.",
            }
        try:
            from neto_pdf_report import write_report_pdf

            result = write_report_pdf(self.workspace)
            return {
                "ok": bool(result.get("ok")),
                "approval_required": False,
                "message": f"PDF raporu hazır: {result.get('path')}",
                "data": result.get("data") or {},
            }
        except Exception as exc:
            return {"ok": False, "approval_required": False, "message": f"PDF raporu oluşturulamadı: {exc}"}

    def dispatch(self, task: str, *, approved: bool = False) -> dict[str, Any]:
        text = " ".join(str(task or "").split())
        lowered = text.casefold()
        if not text:
            return {"handled": False, "message": ""}
        if any(word in lowered for word in self.INPUT_WORDS):
            return {
                "handled": True,
                "ok": False,
                "approval_required": True,
                "message": "Klavye/fare işlemleri için açık kullanıcı onayı ve input_control izni gerekiyor.",
            }
        if any(word in lowered for word in self.OPEN_WORDS):
            result = self.open_program(text, approved=approved)
            return {"handled": True, **result}
        if any(word in lowered for word in self.FILE_WRITE_WORDS):
            result = self.create_file(text, approved=approved)
            return {"handled": True, **result}
        if any(word in lowered for word in self.PDF_WORDS):
            result = self.create_pdf_report(approved=approved)
            return {"handled": True, **result}
        if any(word in lowered for word in self.ERROR_SCAN_WORDS):
            try:
                from neto_error_detection_agent import NetOpsErrorDetectionAgent

                report = NetOpsErrorDetectionAgent(self.workspace).run()
                pdf_path = ""
                try:
                    from neto_pdf_report import write_report_pdf

                    pdf_path = str(write_report_pdf(self.workspace).get("path") or "")
                except Exception:
                    pass
                message = report.summary()
                if pdf_path:
                    message += f" PDF raporu hazır: {pdf_path}"
                return {
                    "handled": True,
                    "ok": report.ok,
                    "message": message,
                    "data": {**report.as_dict(), "pdf_path": pdf_path},
                }
            except Exception as exc:
                return {"handled": True, "ok": False, "message": f"Hata taraması çalışmadı: {exc}"}
        if any(word in lowered for word in self.UI_SCAN_WORDS):
            try:
                from neto_ui_guard_agent import NetOpsUIGuardAgent

                report = NetOpsUIGuardAgent(self.workspace).run()
                pdf_path = ""
                try:
                    from neto_pdf_report import write_report_pdf

                    pdf_path = str(write_report_pdf(self.workspace).get("path") or "")
                except Exception:
                    pass
                message = (
                    "Arayüz kontrolü temiz."
                    if report.ok
                    else f"Arayüz kontrolünde {report.error_count} hata bulundu."
                )
                if pdf_path:
                    message += f" PDF raporu hazır: {pdf_path}"
                return {
                    "handled": True,
                    "ok": report.ok,
                    "message": message,
                    "data": {**report.as_dict(), "pdf_path": pdf_path},
                }
            except Exception as exc:
                return {"handled": True, "ok": False, "message": f"Arayüz kontrolü çalışmadı: {exc}"}
        if any(word in lowered for word in ("sistem durumu", "cpu", "ram", "bilgisayar durumu")):
            data = self.system_status()
            return {"handled": True, "ok": True, "message": "Sistem durumu güvenli biçimde okundu.", "data": data}
        if any(word in lowered for word in ("prosesleri listele", "işlemleri listele", "çalışan programlar", "çalışan işlemler")):
            data = self.process_list()
            return {"handled": True, "ok": True, "message": "Çalışan işlemler listelendi.", "data": {"processes": data}}
        if any(word in lowered for word in ("test et", "doğrula", "dogrula", "derle", "py_compile")):
            plan = self.runner.plan(text)
            run = self.runner.run_safe_steps(plan)
            return {
                "handled": True,
                "ok": run.ok,
                "message": "Güvenli proje doğrulaması tamamlandı." if run.ok else "Proje doğrulamasında hata bulundu.",
                "data": {"results": [result.__dict__ for result in run.results]},
            }
        return {"handled": False, "skills": self.skill_status()}


__all__ = ["AgentToolBridge"]
