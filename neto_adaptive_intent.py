"""Small, dependency-free local intent learner for NetOps.

This is intentionally not a language model. It learns compact feature counts
from accepted NetOps routes. Raw messages and assistant replies are not saved.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from config import KUFUR_LISTESI
except Exception:  # pragma: no cover
    KUFUR_LISTESI = []

MODEL_VERSION = 2
DEFAULT_MODEL_PATH = (
    Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    / "NetoAssistant" / "runtime" / "adaptive_intent_model.json"
)
LEARNABLE_LABELS = {
    "quick_chat", "command", "music_play", "recipe", "web_search",
    "automation_draft",
}
SEED_EXAMPLES = {
    "quick_chat": ("merhaba", "selam", "nasılsın", "naber", "ne yapıyorsun", "burada mısın"),
    "command": ("youtube aç", "google aç", "ekran görüntüsü al", "bilgisayarı kapat", "sesi azalt"),
    "music_play": ("müzik çal", "şarkı aç", "youtube music aç", "bunu oynat"),
    "recipe": ("tarhana çorbası tarifi", "kek nasıl yapılır", "makarna tarifi"),
    "web_search": ("python nedir", "raspberry pi fiyatı", "bugün hava nasıl", "konu hakkında bilgi ver"),
    "automation_draft": ("dosyaları yedekle", "her sabah çalıştır", "bir otomasyon oluştur"),
}

_TR_TABLE = str.maketrans({
    "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
    "ş": "s", "Ş": "s", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_SAFE_LABEL_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


@dataclass(frozen=True)
class IntentPrediction:
    label: str
    confidence: float
    margin: float
    evidence: int


def _contains_abuse(value: Any) -> bool:
    text = str(value or "").casefold().translate(_TR_TABLE)
    for word in KUFUR_LISTESI or []:
        normalized = str(word or "").casefold().translate(_TR_TABLE).strip()
        if normalized and re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text):
            return True
    return False


def normalize_text(value: Any) -> str:
    return " ".join(_TOKEN_RE.findall(str(value or "").casefold().translate(_TR_TABLE)))


def extract_features(value: Any) -> list[str]:
    """Create bounded word and character features for typo-tolerant matching."""
    text = normalize_text(value)
    if not text:
        return []
    features = [f"w:{token}" for token in text.split() if len(token) >= 2]
    compact = f" {text} "
    for size in (3, 4):
        features.extend(
            f"c:{compact[index:index + size]}"
            for index in range(max(0, len(compact) - size + 1))
            if " " not in compact[index:index + size].strip()
        )
    return list(dict.fromkeys(
        "f:" + hashlib.sha256(feature.encode("utf-8")).hexdigest()[:16]
        for feature in features
    ))[:160]


class AdaptiveIntentModel:
    """Conservative local multinomial classifier with confidence gates."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_MODEL_PATH
        self._lock = threading.RLock()
        self._data = self._load()
        if not self._data.get("labels"):
            self._bootstrap()

    def _empty(self) -> dict[str, Any]:
        return {"version": MODEL_VERSION, "examples": 0, "labels": {}, "updatedAt": 0}

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if (
                isinstance(value, dict)
                and value.get("version") == MODEL_VERSION
                and isinstance(value.get("labels"), dict)
            ):
                return value
        except Exception:
            pass
        return self._empty()

    def _bootstrap(self) -> None:
        for label, examples in SEED_EXAMPLES.items():
            for example in examples:
                self._observe(example, label, persist=False)
        self._persist()

    def _label_data(self, label: str) -> dict[str, Any]:
        return self._data.setdefault("labels", {}).setdefault(label, {"examples": 0, "features": {}})

    def _observe(self, text: Any, label: str, *, persist: bool) -> bool:
        if label not in LEARNABLE_LABELS or not _SAFE_LABEL_RE.fullmatch(label) or _contains_abuse(text):
            return False
        features = extract_features(text)
        if not features:
            return False
        record = self._label_data(label)
        record["examples"] = int(record.get("examples") or 0) + 1
        counts = record.setdefault("features", {})
        for feature in features:
            counts[feature] = int(counts.get(feature) or 0) + 1
        self._data["examples"] = int(self._data.get("examples") or 0) + 1
        self._data["updatedAt"] = time.time()
        if len(counts) > 2400:
            record["features"] = dict(sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))[:2400])
        if persist:
            self._persist()
        return True

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix="adaptive_intent_", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def observe(self, text: Any, label: str) -> bool:
        with self._lock:
            return self._observe(text, str(label or "").strip(), persist=True)

    def predict(self, text: Any, *, min_confidence: float = 0.78, min_margin: float = 0.16) -> IntentPrediction | None:
        features = extract_features(text)
        if not features or _contains_abuse(text):
            return None
        with self._lock:
            labels = self._data.get("labels") or {}
            if len(labels) < 2:
                return None
            total_examples = max(1, sum(int(item.get("examples") or 0) for item in labels.values()))
            vocabulary = set()
            for item in labels.values():
                vocabulary.update((item.get("features") or {}).keys())
            vocabulary_size = max(1, len(vocabulary))
            scores = []
            for label, item in labels.items():
                examples = int(item.get("examples") or 0)
                if examples <= 0:
                    continue
                counts = item.get("features") or {}
                total_features = max(1, sum(int(value) for value in counts.values()))
                score = math.log(examples / total_examples)
                evidence = 0
                for feature in features:
                    count = int(counts.get(feature) or 0)
                    evidence += bool(count)
                    score += math.log((count + 1) / (total_features + vocabulary_size))
                scores.append((label, score, evidence))
            if not scores:
                return None
            scores.sort(key=lambda item: item[1], reverse=True)
            top = scores[0]
            second_score = scores[1][1] if len(scores) > 1 else top[1] - 1
            margin = top[1] - second_score
            logits = [math.exp(max(-60.0, score - top[1])) for _, score, _ in scores]
            confidence = logits[0] / max(1e-9, sum(logits))
            if top[2] < 2 or confidence < min_confidence or margin < min_margin:
                return None
            return IntentPrediction(top[0], round(confidence, 4), round(margin, 4), int(top[2]))

    def status(self) -> dict[str, Any]:
        with self._lock:
            labels = self._data.get("labels") or {}
            return {
                "version": MODEL_VERSION,
                "examples": int(self._data.get("examples") or 0),
                "labels": {key: int(value.get("examples") or 0) for key, value in labels.items()},
                "path": str(self.path),
            }


__all__ = ["AdaptiveIntentModel", "IntentPrediction", "extract_features", "normalize_text"]
