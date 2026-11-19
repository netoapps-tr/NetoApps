from neto_builtin_skills import builtin_skills, handle


def test_builtin_catalog_contains_modular_read_only_skills() -> None:
    ids = {item.skill_id for item in builtin_skills()}

    assert {"system", "media", "devices", "help", "recovery"}.issubset(ids)


def test_system_skill_uses_injected_metrics_without_touching_the_system() -> None:
    result = handle(
        "RAM durumunu göster",
        metrics_provider=lambda: {"cpu": 12, "ram": 64, "ram_used_gb": 10.2, "ram_total_gb": 15.9},
    )

    assert result == "CPU %12 • RAM %64 (10.2/15.9 GB)"


def test_single_metric_queries_do_not_duplicate_their_answer() -> None:
    metrics = {
        "cpu": 12,
        "ram": 64,
        "ram_used_gb": 10.2,
        "ram_total_gb": 15.9,
        "disk_used_gb": 100.0,
        "disk_total_gb": 500.0,
        "battery": 88,
    }

    assert handle("CPU durumu", metrics_provider=lambda: metrics) == "CPU %12"
    assert handle("pil durumu", metrics_provider=lambda: metrics) == "Pil %88"


def test_help_skill_exposes_more_commands() -> None:
    result = handle("komutlar")

    assert result is not None
    assert "disk durumu" in result
    assert "pil durumu" in result
    assert "şimdi çalan" in result


def test_unknown_text_is_left_for_the_existing_conversation_engine() -> None:
    assert handle("bana bir hikaye anlat") is None


def test_recovery_skill_reports_a_review_first_plan() -> None:
    result = handle("Recovery Mesh ile kritik hataları bul ve kendini onar")
    assert result is not None
    assert "Recovery Mesh" in result
    assert "onay" in result.casefold()
