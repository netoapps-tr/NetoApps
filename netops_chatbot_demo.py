"""Standalone NetOps chatbot demo.

This is intentionally separate from the NetOps launcher. It reuses the local
Harbilig conversation engine but stores demo memory in its own directory.
"""

from __future__ import annotations

import html
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from netops_harbilig_engine import get_engine


DEMO_DATA_DIR = Path(__file__).with_name("chatbot_demo_data")
SAFE_ERROR = "Şu an cevap üretirken bir sorun oluştu. Daha kısa bir mesajla tekrar dene."


@dataclass(frozen=True)
class DemoReply:
    text: str
    intent: str
    source: str
    cached: bool = False
    learned: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class StandaloneChatbot:
    """Small public boundary for evaluating the chatbot before integration."""

    def __init__(
        self,
        *,
        project_dir: str | Path | None = None,
        internet_enabled: bool = True,
    ) -> None:
        self.project_dir = Path(project_dir or DEMO_DATA_DIR).expanduser().resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._session_turns: list[dict[str, str]] = []
        self.engine = get_engine(
            project_dir=self.project_dir,
            internet_enabled=internet_enabled,
            max_sources=3,
        )

    def ask(self, message: Any, *, agent_mode: bool = False) -> DemoReply:
        text = str(message or "").strip()
        if not text:
            return DemoReply(
                text="Bir şey yazmadın.",
                intent="empty",
                source="standalone_chatbot",
                metadata={"agent_mode": bool(agent_mode), "intent": "empty"},
            )

        try:
            result = self.engine.answer(text, agent_mode=agent_mode)
            metadata = dict(result.as_dict())
            metadata["agent_mode"] = bool(agent_mode)
            metadata["intent"] = result.intent
            reply = DemoReply(
                text=result.text,
                intent=result.intent,
                source=result.source,
                cached=bool(result.cached),
                learned=bool(result.learned),
                metadata=metadata,
            )
            self._session_turns.extend(
                (
                    {"role": "user", "text": text},
                    {"role": "assistant", "text": reply.text},
                )
            )
            del self._session_turns[:-20]
            return reply
        except Exception as exc:  # Keep the demo responsive during evaluation.
            reply = DemoReply(
                text=SAFE_ERROR,
                intent="error",
                source="standalone_chatbot",
                metadata={"agent_mode": bool(agent_mode), "error": str(exc)},
            )
            self._session_turns.extend(
                (
                    {"role": "user", "text": text},
                    {"role": "assistant", "text": reply.text},
                )
            )
            del self._session_turns[:-20]
            return reply

    def turns(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(turn) for turn in self._session_turns)

    def clear_session(self) -> None:
        self._session_turns.clear()

    @staticmethod
    def suggested_prompts() -> tuple[str, ...]:
        return (
            "Kendini tanıt",
            "Ne yapabilirsin?",
            "Bana bir plan çıkar",
            "İnternetten ara: Python nedir?",
        )


class _AskThread(QThread):
    reply_ready = Signal(object)

    def __init__(self, chatbot: StandaloneChatbot, message: str, agent_mode: bool) -> None:
        super().__init__()
        self.chatbot = chatbot
        self.message = message
        self.agent_mode = agent_mode

    def run(self) -> None:
        self.reply_ready.emit(self.chatbot.ask(self.message, agent_mode=self.agent_mode))


class StandaloneChatbotWindow(QMainWindow):
    """A richer chat surface for trying the engine without NetOps UI."""

    _WELCOME = "Merhaba. Ben NetOps Chatbot demosuyum. Bir konu yaz, birlikte ilerleyelim."

    def __init__(self, chatbot: StandaloneChatbot | None = None) -> None:
        super().__init__()
        self.chatbot = chatbot or StandaloneChatbot()
        self._ask_thread: _AskThread | None = None
        self._visible_turns: list[tuple[str, str]] = [("assistant", self._WELCOME)]
        self._typing = False
        self._stream_text = ""
        self._stream_index = 0
        self._pending_reply: DemoReply | None = None
        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(14)
        self._stream_timer.timeout.connect(self._reveal_reply)

        self.setWindowTitle("NetOps Chatbot Demo")
        self.resize(980, 720)
        self.setMinimumSize(680, 520)

        root = QWidget()
        root.setObjectName("demoRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)

        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header = QHBoxLayout(header_card)
        header.setContentsMargins(16, 14, 16, 14)
        title_box = QVBoxLayout()
        title = QLabel("NetOps Chatbot")
        title.setObjectName("title")
        subtitle = QLabel("Yerel çekirdek · ayrı demo alanı · NetOps’a aktarılmadı")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._core_badge = QLabel("●  LOCAL CORE")
        self._core_badge.setObjectName("coreBadge")
        header.addWidget(self._core_badge)
        self._mode_check = QCheckBox("Agent modu")
        self._mode_check.setToolTip("Daha serbest asistan yönlendirmesini dene")
        header.addWidget(self._mode_check)
        self._clear_button = QPushButton("Yeni sohbet")
        self._clear_button.setObjectName("clearButton")
        self._clear_button.clicked.connect(self._clear_chat)
        header.addWidget(self._clear_button)
        layout.addWidget(header_card)

        self._output = QTextBrowser()
        self._output.setObjectName("chatOutput")
        self._output.setOpenExternalLinks(False)
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Konuşma burada görünecek...")
        layout.addWidget(self._output, 1)

        suggestions = QHBoxLayout()
        suggestions.setSpacing(8)
        for prompt in self.chatbot.suggested_prompts():
            button = QPushButton(prompt)
            button.setObjectName("suggestionButton")
            button.clicked.connect(lambda _checked=False, value=prompt: self._use_prompt(value))
            suggestions.addWidget(button)
        layout.addLayout(suggestions)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(8, 7, 8, 7)
        self._input = QLineEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Mesajını yaz... Enter ile gönder")
        self._input.returnPressed.connect(self._submit)
        self._send_button = QPushButton("Gönder  →")
        self._send_button.setObjectName("sendButton")
        self._send_button.clicked.connect(self._submit)
        composer_layout.addWidget(self._input, 1)
        composer_layout.addWidget(self._send_button)
        layout.addWidget(composer)

        self._status = QLabel("Hazır · Oturum hafızası ayrı klasörde tutulur")
        self._status.setObjectName("status")
        layout.addWidget(self._status)

        self.setCentralWidget(root)
        self.setStyleSheet(
            "QWidget#demoRoot { background: #0A0F1C; color: #E8EEF8; }"
            "QFrame#headerCard { background: #111A2A; border: 1px solid #283C59; border-radius: 16px; }"
            "QLabel#title { color: #F4F7FB; font-size: 24px; font-weight: 700; }"
            "QLabel#subtitle, QLabel#status { color: #91A4BE; font-size: 12px; }"
            "QLabel#coreBadge { background: #123A35; color: #6DE7B7; border: 1px solid #1C785D; border-radius: 10px; padding: 7px 10px; font-size: 11px; font-weight: 700; }"
            "QTextBrowser#chatOutput { background: #101827; color: #E8EEF8; border: 1px solid #263A56; border-radius: 16px; padding: 12px; font-size: 14px; }"
            "QFrame#composer { background: #111A2A; border: 1px solid #3B82F6; border-radius: 16px; }"
            "QLineEdit#chatInput { background: transparent; color: #F4F7FB; border: none; padding: 10px 12px; font-size: 14px; }"
            "QPushButton#sendButton { background: #3B82F6; color: white; border: 0; border-radius: 11px; padding: 10px 18px; font-weight: 700; }"
            "QPushButton#sendButton:hover { background: #5B9DFF; }"
            "QPushButton#sendButton:disabled { background: #34445D; color: #91A4BE; }"
            "QPushButton#clearButton, QPushButton#suggestionButton { background: #172337; color: #BFD0E5; border: 1px solid #2B4262; border-radius: 10px; padding: 7px 10px; }"
            "QPushButton#clearButton:hover, QPushButton#suggestionButton:hover { background: #203552; border-color: #5B9DFF; color: white; }"
            "QCheckBox { color: #C8D4E5; spacing: 8px; }"
        )
        self._render_messages()

    @staticmethod
    def _bubble(role: str, text: str) -> str:
        safe = html.escape(str(text)).replace("\n", "<br>")
        is_user = role == "user"
        label = "SEN" if is_user else "NETOPS"
        background = "#1B3A63" if is_user else "#172333"
        border = "#3B82F6" if is_user else "#2D4968"
        align = "right" if is_user else "left"
        return (
            f'<div style="margin: 10px 4px; text-align: {align};">'
            f'<div style="color: #8FA6C2; font-size: 10px; font-weight: 700; margin-bottom: 4px;">{label}</div>'
            f'<div style="background: {background}; border: 1px solid {border}; border-radius: 12px; '
            f'padding: 10px 13px; color: #E8EEF8;">{safe}</div></div>'
        )

    def _render_messages(self) -> None:
        blocks = [self._bubble(role, text) for role, text in self._visible_turns]
        if self._typing:
            blocks.append(self._bubble("assistant", "Düşünüyor <span style='color:#5B9DFF;'>•••</span>"))
        if self._stream_text:
            blocks.append(self._bubble("assistant", self._stream_text[: self._stream_index]))
        self._output.setHtml("<body style='background:#101827;'>" + "".join(blocks) + "</body>")
        scrollbar = self._output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _use_prompt(self, prompt: str) -> None:
        if self._ask_thread is not None and self._ask_thread.isRunning():
            return
        self._input.setText(prompt)
        self._input.setFocus()

    def _clear_chat(self) -> None:
        if self._ask_thread is not None and self._ask_thread.isRunning():
            return
        self._stream_timer.stop()
        self.chatbot.clear_session()
        self._visible_turns = [("assistant", "Yeni sohbet hazır. Ne üzerine konuşalım?")]
        self._typing = False
        self._stream_text = ""
        self._pending_reply = None
        self._status.setText("Hazır · Yeni oturum")
        self._render_messages()
        self._input.setFocus()

    def _submit(self) -> None:
        if self._ask_thread is not None and self._ask_thread.isRunning():
            return
        if self._stream_timer.isActive():
            return
        message = self._input.text().strip()
        if not message:
            return

        agent_mode = self._mode_check.isChecked()
        self._visible_turns.append(("user", message))
        self._typing = True
        self._render_messages()
        self._input.clear()
        self._input.setEnabled(False)
        self._send_button.setEnabled(False)
        self._clear_button.setEnabled(False)
        self._status.setText("NetOps düşünüyor...")

        thread = _AskThread(self.chatbot, message, agent_mode)
        thread.reply_ready.connect(self._show_reply)
        thread.finished.connect(self._thread_finished)
        self._ask_thread = thread
        thread.start()

    def _show_reply(self, reply: DemoReply) -> None:
        self._typing = False
        self._pending_reply = reply
        self._stream_text = reply.text
        self._stream_index = 0
        self._status.setText("Yanıt hazırlanıyor...")
        self._render_messages()
        self._stream_timer.start()

    def _reveal_reply(self) -> None:
        self._stream_index = min(len(self._stream_text), self._stream_index + 13)
        self._render_messages()
        if self._stream_index < len(self._stream_text):
            return

        self._stream_timer.stop()
        reply = self._pending_reply
        if reply is not None:
            self._visible_turns.append(("assistant", reply.text))
            details = reply.intent
            if reply.cached:
                details += " · hafızadan"
            if reply.learned:
                details += " · öğrenildi"
            self._status.setText(f"Hazır · {details}")
        self._pending_reply = None
        self._stream_text = ""
        self._render_messages()
        self._input.setEnabled(True)
        self._send_button.setEnabled(True)
        self._clear_button.setEnabled(True)
        self._input.setFocus()

    def _thread_finished(self) -> None:
        if self._ask_thread is not None:
            self._ask_thread.deleteLater()
        self._ask_thread = None

    def closeEvent(self, event: Any) -> None:
        self._stream_timer.stop()
        if self._ask_thread is not None and self._ask_thread.isRunning():
            self._ask_thread.wait(1500)
        super().closeEvent(event)


def run_demo() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = StandaloneChatbotWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_demo())


__all__ = ["DEMO_DATA_DIR", "DemoReply", "StandaloneChatbot", "StandaloneChatbotWindow", "run_demo"]
