from neto_text_assistant import NetOpsTextAssistant, SAFE_FALLBACK


def test_text_assistant_routes_commands_and_keeps_history() -> None:
    assistant = NetOpsTextAssistant(command_router=lambda text: f"yanıt: {text}")

    assert assistant.respond("saat kaç") == "yanıt: saat kaç"
    assert assistant.history() == (({"message": "saat kaç", "reply": "yanıt: saat kaç"}),)


def test_text_assistant_falls_back_when_router_crashes() -> None:
    logs = []

    def broken_router(_text):
        raise RuntimeError("router kapalı")

    assistant = NetOpsTextAssistant(
        command_router=broken_router,
        fallback_responder=lambda text: f"AI: {text}",
        logger=logs.append,
    )

    result = assistant.respond_result("merhaba")

    assert result.text == "AI: merhaba"
    assert result.source == "netops_ai_fallback"
    assert logs == []
    assert result.metadata["router_errors"] == ("command_router: router kapalı",)


def test_text_assistant_never_returns_blank_when_every_engine_fails() -> None:
    assistant = NetOpsTextAssistant(
        command_router=lambda _text: (_ for _ in ()).throw(RuntimeError("router")),
        fallback_responder=lambda _text: (_ for _ in ()).throw(RuntimeError("ai")),
    )

    result = assistant.respond_result("test")

    assert result.text == SAFE_FALLBACK
    assert result.kind == "fallback"


def test_text_assistant_does_not_retry_callback_type_errors() -> None:
    calls = []

    def broken_router(_text, **_kwargs):
        calls.append(_text)
        raise TypeError("callback içi hata")

    assistant = NetOpsTextAssistant(
        command_router=broken_router,
        fallback_responder=lambda _text: "yedek yanıt",
    )

    assert assistant.respond("tek deneme") == "yedek yanıt"
    assert calls == ["tek deneme"]


def test_text_assistant_previews_multi_step_tasks_before_running_them() -> None:
    calls = []
    assistant = NetOpsTextAssistant(
        command_router=lambda text: calls.append(text) or f"yanıt: {text}",
    )

    result = assistant.respond_result("RAM'i göster sonra müziği durdur")

    assert result.kind == "plan"
    assert result.source == "netops_task_planner"
    assert calls == []
    assert "Görev planı hazırlandı" in result.text


def test_text_assistant_executes_pending_plan_only_after_confirmation() -> None:
    calls = []
    assistant = NetOpsTextAssistant(
        command_router=lambda text: calls.append(text) or f"yanıt: {text}",
    )

    assistant.respond("RAM'i göster sonra müziği durdur")
    result = assistant.respond_result("onayla")

    assert result.kind == "plan_result"
    assert calls == ["RAM'i göster", "müziği durdur"]
    assert "1." in result.text and "2." in result.text


def test_text_assistant_can_cancel_pending_plan() -> None:
    assistant = NetOpsTextAssistant(command_router=lambda text: text)

    assistant.respond("RAM'i göster sonra müziği durdur")
    result = assistant.respond_result("iptal")

    assert result.kind == "plan_cancelled"
    assert "iptal edildi" in result.text.casefold()
