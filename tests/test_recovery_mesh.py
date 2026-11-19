from neto_recovery_mesh import build_recovery_plan, recovery_skill_catalog


def test_clean_report_does_not_schedule_a_repair():
    plan = build_recovery_plan({"files_scanned": 4, "error_count": 0, "critical_count": 0, "findings": []})
    assert plan["status"] == "healthy"
    assert plan["requires_confirmation"] is False
    assert plan["steps"] == []


def test_critical_report_requires_backup_and_explicit_approval():
    plan = build_recovery_plan(
        {
            "files_scanned": 4,
            "error_count": 2,
            "critical_count": 1,
            "findings": [{"severity": "critical", "message": "Traceback"}],
        }
    )
    assert plan["status"] == "approval_required"
    assert plan["requires_confirmation"] is True
    assert [step["id"] for step in plan["steps"]] == [
        "diagnose",
        "backup",
        "repair_review",
        "verify",
        "rollback_on_failure",
    ]
    assert plan["steps"][1]["requires_confirmation"] is True


def test_recovery_catalog_is_explicit_and_non_destructive_by_default():
    catalog = recovery_skill_catalog()
    names = {item["id"] for item in catalog}
    assert names == {"observe", "classify", "backup", "verify", "rollback"}
    assert all(item["default_mode"] == "review" for item in catalog)
