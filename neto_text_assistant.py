"""Canonical text-assistant boundary for the NetOps desktop UI.

The project has several useful local engines. This module keeps them behind
one small, deterministic boundary so the text box never has to know which
router, skill, or fallback produced a reply.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import inspect
from typing import Any, Callable

from neto_task_planner import (
    TaskPlan,
    build_task_plan,
    format_task_plan,
    is_cancellation,
    is_confirmation,
)


ReplyCallback = Callable[..., Any]

SAFE_FALLBACK = (
    "NetOps şu an bu isteği tamamlayamadı. "
    "Daha kısa bir komutla tekrar deneyebilirsin."
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _extract_text(value: Any) -> str:
    if isinstance(value, dict):
        return _clean_text(value.get("text") or value.get("message") or value.get("response"))
    text = getattr(value, "text", None)
    return _clean_text(text if text is not None else value)


def _call(callback: ReplyCallback, text: str, agent_mode: bool) -> Any:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        parameters = signature.parameters.values()
        accepts_agent_mode = (
            "agent_modu" in signature.parameters
            or any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters)
        )
        if accepts_agent_mode:
            return callback(text, agent_modu=agent_mode)
        return callback(text)

    # Some extension callables do not expose a signature. Prefer the simpler
    # call because it cannot accidentally trigger a second side effect.
    try:
        return callback(text)
    except TypeError as exc:
        if "agent_modu" not in str(exc):
            raise
        return callback(text, agent_modu=agent_mode)


@dataclass(frozen=True)
class TextAssistantResponse:
    text: str
    kind: str = "response"
    source: str = "netops_text_assistant"
    raw_input: str = ""
    agent_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class NetOpsTextAssistant:
    """Route every desktop text message through one safe local boundary."""

    def __init__(
        self,
        *,
        command_router: ReplyCallback | None = None,
        fallback_responder: ReplyCallback | None = None,
        planner: Callable[[str], TaskPlan | None] | None = build_task_plan,
        logger: Callable[[str], None] | None = None,
        history_limit: int = 12,
    ) -> None:
        self.command_router = command_router
        self.fallback_responder = fallback_responder
        self.planner = planner
        self.logger = logger
        self._history: deque[dict[str, str]] = deque(maxlen=max(1, int(history_limit)))
        self._pending_plan: TaskPlan | None = None

    def _log(self, message: str) -> None:
        if callable(self.logger):
            try:
                self.logger(message)
            except Exception:
                pass

    @staticmethod
    def _kind(text: str) -> str:
        if text.startswith("__"):
            return "command"
        return "response"

    def respond_result(self, message: Any, *, agent_mode: bool = False) -> TextAssistantResponse:
        raw = _clean_text(message)
        if not raw:
            return TextAssistantResponse(
                "Bir şey yazmadın.",
                kind="empty",
                raw_input="",
                agent_mode=agent_mode,
            )

        if self._pending_plan is not None:
            if is_cancellation(raw):
                self._pending_plan = None
                result = TextAssistantResponse(
                    "Görev planı iptal edildi.",
                    kind="plan_cancelled",
                    source="netops_task_planner",
                    raw_input=raw,
                    agent_mode=agent_mode,
                )
                self._remember(raw, result.text)
                return result
            if is_confirmation(raw):
                return self._execute_pending_plan(raw, agent_mode=agent_mode)

        if callable(self.planner):
            try:
                plan = self.planner(raw)
            except Exception as exc:
                self._log(f"[TASK_PLANNER_ERROR] {exc}")
                plan = None
            if plan is not None:
                self._pending_plan = plan
                result = TextAssistantResponse(
                    format_task_plan(plan, can_execute=callable(self.command_router)),
                    kind="plan",
                    source="netops_task_planner",
                    raw_input=raw,
                    agent_mode=agent_mode,
                    metadata={"plan": plan.as_dict()},
                )
                self._remember(raw, result.text)
                return result

        errors: list[str] = []
        if callable(self.command_router):
            try:
                text = _extract_text(_call(self.command_router, raw, agent_mode))
                if text:
                    result = TextAssistantResponse(
                        text,
                        kind=self._kind(text),
                        source="netops_command_router",
                        raw_input=raw,
                        agent_mode=agent_mode,
                    )
                    self._remember(raw, result.text)
                    return result
            except Exception as exc:
                errors.append(f"command_router: {exc}")

        if callable(self.fallback_responder):
            try:
                text = _extract_text(_call(self.fallback_responder, raw, agent_mode))
                if text:
                    result = TextAssistantResponse(
                        text,
                        kind=self._kind(text),
                        source="netops_ai_fallback",
                        raw_input=raw,
                        agent_mode=agent_mode,
                        metadata={"router_errors": tuple(errors)} if errors else {},
                    )
                    self._remember(raw, result.text)
                    return result
            except Exception as exc:
                errors.append(f"fallback_responder: {exc}")

        if errors:
            self._log("[TEXT_ASSISTANT_ERROR] " + " | ".join(errors))
        result = TextAssistantResponse(
            SAFE_FALLBACK,
            kind="fallback",
            source="netops_text_assistant",
            raw_input=raw,
            agent_mode=agent_mode,
            metadata={"errors": tuple(errors)} if errors else {},
        )
        self._remember(raw, result.text)
        return result

    def _execute_pending_plan(self, raw: str, *, agent_mode: bool) -> TextAssistantResponse:
        plan = self._pending_plan
        if plan is None:
            return TextAssistantResponse(
                'Bekleyen görev yok. Önce "sonra" ile iki adımlı bir istek yaz.',
                kind="plan_result",
                source="netops_task_planner",
                raw_input=raw,
                agent_mode=agent_mode,
            )
        if not callable(self.command_router):
            return TextAssistantResponse(
                "Görev yürütücüsü bağlı değil; plan çalıştırılmadı.",
                kind="plan_result",
                source="netops_task_planner",
                raw_input=raw,
                agent_mode=agent_mode,
                metadata={"plan": plan.as_dict()},
            )

        lines = ["Görev yürütülüyor:"]
        metadata_steps: list[dict[str, Any]] = []
        for step in plan.steps:
            try:
                value = _extract_text(_call(self.command_router, step.text, False))
            except Exception as exc:
                self._log(f"[TASK_PLAN_STEP_ERROR] {step.index}: {exc}")
                value = "Bu adım çalıştırılamadı."
            if not value:
                value = "Bu adım yanıt üretmedi."
            lines.append(f"{step.index}. {step.category}: {value}")
            metadata_steps.append({"step": step.as_dict(), "response": value})

        self._pending_plan = None
        result = TextAssistantResponse(
            "\n".join(lines),
            kind="plan_result",
            source="netops_task_planner",
            raw_input=raw,
            agent_mode=agent_mode,
            metadata={"plan": plan.as_dict(), "results": metadata_steps},
        )
        self._remember(raw, result.text)
        return result

    def respond(self, message: Any, *, agent_mode: bool = False) -> str:
        return self.respond_result(message, agent_mode=agent_mode).text

    def _remember(self, message: str, reply: str) -> None:
        self._history.append({"message": message, "reply": reply})

    def history(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(item) for item in self._history)

    def clear_history(self) -> None:
        self._history.clear()


__all__ = ["NetOpsTextAssistant", "TextAssistantResponse", "SAFE_FALLBACK"]
