from pathlib import Path

from netops_chatbot_demo import StandaloneChatbot


def test_standalone_chatbot_answers_without_touching_netops_memory(tmp_path: Path) -> None:
    demo = StandaloneChatbot(project_dir=tmp_path, internet_enabled=False)

    reply = demo.ask("merhaba")

    assert reply.text
    assert reply.intent
    assert reply.source
    assert (tmp_path / "netops_memory.json").exists()


def test_standalone_chatbot_returns_structured_result_and_agent_mode(tmp_path: Path) -> None:
    demo = StandaloneChatbot(project_dir=tmp_path, internet_enabled=False)

    reply = demo.ask("ne yapabilirsin", agent_mode=True)

    assert reply.text
    assert reply.metadata["agent_mode"] is True
    assert reply.metadata["intent"] == reply.intent


def test_standalone_chatbot_keeps_session_turns_and_can_start_new_chat(tmp_path: Path) -> None:
    demo = StandaloneChatbot(project_dir=tmp_path, internet_enabled=False)

    demo.ask("merhaba")
    turns = demo.turns()

    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"
    assert demo.suggested_prompts()

    demo.clear_session()

    assert demo.turns() == ()


def test_demo_window_entrypoint_is_separate_from_netops_launcher() -> None:
    source = Path("netops_chatbot_demo.py").read_text(encoding="utf-8")

    assert "class StandaloneChatbotWindow" in source
    assert "QApplication" in source
    assert "QTextBrowser" in source
    assert "Düşünüyor" in source
    assert "Yeni sohbet" in source
    assert "if __name__ == \"__main__\"" in source
    assert "asistan beta.py" not in source
