from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


Resolver = Callable[..., Any]


@dataclass(slots=True)
class AssistantResult:
    text: str
    kind: str = "response"
    source: str = "assistant"
    command: str | None = None
    raw_input: str = ""
    normalized_input: str = ""
    agent_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind,
            "source": self.source,
            "command": self.command,
            "raw_input": self.raw_input,
            "normalized_input": self.normalized_input,
            "agent_mode": self.agent_mode,
            "metadata": dict(self.metadata),
        }


def _normalize_text(text: Any) -> str:
    return str(text or "").strip()


def _call_resolver(resolver: Resolver, text: str, agent_mode: bool) -> Any:
    try:
        return resolver(text, agent_modu=agent_mode)
    except TypeError as first_error:
        try:
            return resolver(text)
        except TypeError:
            raise first_error


def _coerce_result(
    value: Any,
    *,
    raw_input: str,
    normalized_input: str,
    agent_mode: bool,
    source: str,
    default_kind: str,
    metadata: Optional[dict[str, Any]] = None,
) -> AssistantResult | None:
    if isinstance(value, AssistantResult):
        if not value.raw_input:
            value.raw_input = raw_input
        if not value.normalized_input:
            value.normalized_input = normalized_input
        if metadata:
            merged = dict(value.metadata)
            merged.update(metadata)
            value.metadata = merged
        return value

    if value is None:
        return None

    payload: dict[str, Any] = {}
    if isinstance(value, dict):
        payload = dict(value)
        text = payload.get("text") or payload.get("message") or payload.get("response")
        text = _normalize_text(text)
        if not text:
            return None
        kind = str(payload.get("kind") or default_kind or "response")
        command = payload.get("command")
        source_value = str(payload.get("source") or source or "assistant")
        merged_metadata = dict(metadata or {})
        extra_metadata = payload.get("metadata")
        if isinstance(extra_metadata, dict):
            merged_metadata.update(extra_metadata)
        if command is None and text.startswith("__"):
            command = text
            if kind == "response":
                kind = "command"
        return AssistantResult(
            text=text,
            kind=kind,
            source=source_value,
            command=str(command) if command is not None else None,
            raw_input=raw_input,
            normalized_input=normalized_input,
            agent_mode=agent_mode,
            metadata=merged_metadata,
        )

    text = _normalize_text(value)
    if not text:
        return None

    kind = default_kind or "response"
    command = None
    if text.startswith("__"):
        kind = "command"
        command = text

    return AssistantResult(
        text=text,
        kind=kind,
        source=source,
        command=command,
        raw_input=raw_input,
        normalized_input=normalized_input,
        agent_mode=agent_mode,
        metadata=dict(metadata or {}),
    )


class AssistantEngine:
    def __init__(
        self,
        *,
        quick_resolver: Resolver | None = None,
        ai_responder: Resolver | None = None,
        normalizer: Callable[[Any], str] | None = None,
        name: str = "assistant",
    ) -> None:
        self.quick_resolver = quick_resolver
        self.ai_responder = ai_responder
        self.normalizer = normalizer or _normalize_text
        self.name = name

    def normalize(self, text: Any) -> str:
        try:
            return _normalize_text(self.normalizer(text))
        except Exception:
            return _normalize_text(text)

    def route(
        self,
        text: Any,
        *,
        agent_modu: bool = False,
        allow_quick: bool | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AssistantResult:
        raw_input = _normalize_text(text)
        normalized_input = self.normalize(text)
        merged_metadata = dict(metadata or {})

        if not normalized_input:
            return AssistantResult(
                text="Bir şey yazmadın.",
                kind="empty",
                source=self.name,
                raw_input=raw_input,
                normalized_input=normalized_input,
                agent_mode=agent_modu,
                metadata=merged_metadata,
            )

        if allow_quick is None:
            allow_quick = not agent_modu

        if allow_quick and callable(self.quick_resolver):
            try:
                quick_value = _call_resolver(self.quick_resolver, normalized_input, agent_mode=agent_modu)
            except Exception as exc:
                quick_value = None
                merged_metadata["quick_error"] = str(exc)
            quick_result = _coerce_result(
                quick_value,
                raw_input=raw_input,
                normalized_input=normalized_input,
                agent_mode=agent_modu,
                source="quick",
                default_kind="quick",
                metadata=merged_metadata,
            )
            if quick_result is not None:
                return quick_result

        responder = self.ai_responder
        if not callable(responder):
            return AssistantResult(
                text="Asistan motorunda cevaplayıcı bulunamadı.",
                kind="error",
                source=self.name,
                raw_input=raw_input,
                normalized_input=normalized_input,
                agent_mode=agent_modu,
                metadata=merged_metadata,
            )

        try:
            ai_value = _call_resolver(responder, raw_input, agent_mode=agent_modu)
        except Exception as exc:
            return AssistantResult(
                text=f"Hata: {exc}",
                kind="error",
                source=self.name,
                raw_input=raw_input,
                normalized_input=normalized_input,
                agent_mode=agent_modu,
                metadata=merged_metadata,
            )

        ai_result = _coerce_result(
            ai_value,
            raw_input=raw_input,
            normalized_input=normalized_input,
            agent_mode=agent_modu,
            source="ai",
            default_kind="response",
            metadata=merged_metadata,
        )
        if ai_result is not None:
            return ai_result

        return AssistantResult(
            text="Bir şey yazmadın.",
            kind="empty",
            source=self.name,
            raw_input=raw_input,
            normalized_input=normalized_input,
            agent_mode=agent_modu,
            metadata=merged_metadata,
        )

    __call__ = route

