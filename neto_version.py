"""NetOps v10 release source of truth.

Keeping release metadata in one tiny module prevents the EXE, UI and updater
from drifting apart during a release.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_VERSION = "1.53.1"
APP_CHANNEL = "stable"
RELEASE_NAME = "NetOps One"
RELEASE_TAG = f"v{APP_VERSION}"
RELEASE_REPOSITORY = "https://github.com/netoapps-tr/NetoApps"
RELEASE_HIGHLIGHTS = (
    "QEMU tabanlı, kaynak sınırları korunan sanal masaüstü temeli",
    "NetOps içinden sanal masaüstü başlatma, durum ve güvenli durdurma komutları",
    "Telefon/Android bağlantısından bağımsız PC odaklı 1.53.1 çekirdeği",
    "Dahili Now Playing ve Now Playing Atmosferi",
    "Kasma azaltılmış, kapanmış widget korumalı animasyon motoru",
    "Sistem ayarlarında hızlı açılış ve arka plan kontrolleri",
    "Dosya bazlı, SHA-256 doğrulamalı güncelleme sistemi",
    "Güvenli 1.41 rollback geçmişi ve gizli kurtarma kodu",
    "Yerel hata tespit, UI koruma ve eklenti-doctor agentları",
)


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _clean_version(value: object) -> str:
    text = str(value or "").strip().lstrip("vV")
    match = __import__("re").search(r"\d+(?:\.\d+){1,5}", text)
    return match.group(0) if match else text


def get_app_version() -> str:
    env_value = _clean_version(os.environ.get("NETO_APP_VERSION"))
    if env_value:
        return env_value
    return _clean_version(APP_VERSION) or "1.53.1"


def write_installed_version(value: object) -> str:
    version = _clean_version(value)
    if not version:
        raise ValueError("Geçerli bir sürüm numarası bulunamadı.")
    os.environ["NETO_APP_VERSION"] = version
    return version


def version_label(prefix: str = "v") -> str:
    return f"{prefix}{get_app_version()}"


def app_title(language: str = "tr") -> str:
    if str(language).lower().startswith("en"):
        return f"NetOps v{get_app_version()}"
    return f"NetOps v{get_app_version()}"


APP_TITLE_TR = app_title("tr")
APP_TITLE_EN = app_title("en")
