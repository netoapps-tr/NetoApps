from __future__ import annotations

from neto_task_planner import build_task_plan, format_task_plan


def test_build_task_plan_splits_turkish_multi_step_request() -> None:
    plan = build_task_plan("telefonumdaki RAM'i söyle, sonra müziği durdur")

    assert plan is not None
    assert [step.text for step in plan.steps] == [
        "telefonumdaki RAM'i söyle",
        "müziği durdur",
    ]
    assert plan.steps[0].category == "Cihaz"
    assert plan.steps[1].category == "Now Playing"
    assert plan.requires_confirmation is True


def test_task_planner_marks_destructive_steps_as_high_risk() -> None:
    plan = build_task_plan("sistem durumunu göster sonra bilgisayarı yeniden başlat")

    assert plan is not None
    assert plan.risk_level == "yüksek"
    assert plan.steps[1].requires_confirmation is True
    assert "onay" in format_task_plan(plan, can_execute=True).casefold()


def test_single_step_questions_are_not_intercepted() -> None:
    assert build_task_plan("saat kaç") is None


def test_media_control_is_not_labelled_as_destructive_system_action() -> None:
    plan = build_task_plan("RAM'i göster sonra müziği durdur")

    assert plan is not None
    assert plan.risk_level == "düşük"
    assert plan.steps[1].requires_confirmation is False


def test_plan_format_is_explicitly_preview_only_until_confirmed() -> None:
    plan = build_task_plan("RAM'i göster sonra hava durumunu söyle")

    assert plan is not None
    text = format_task_plan(plan, can_execute=False)
    assert "Görev planı hazırlandı" in text
    assert "1." in text and "2." in text
    assert "henüz çalıştırılmadı" in text
