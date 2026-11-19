from __future__ import annotations

from pathlib import Path

import neto_virtual_desktop as virtual_desktop


def test_config_clamps_resources_to_safe_bounds() -> None:
    config = virtual_desktop.VirtualDesktopConfig(
        project_root=Path("."),
        memory_mb=99999,
        cpus=99,
    ).normalized()

    assert config.memory_mb == 4096
    assert config.cpus == 4

    low = virtual_desktop.VirtualDesktopConfig(
        project_root=Path("."),
        memory_mb=1,
        cpus=0,
    ).normalized()
    assert low.memory_mb == 512
    assert low.cpus == 1


def test_build_qemu_command_is_snapshot_first_and_does_not_use_shell() -> None:
    config = virtual_desktop.VirtualDesktopConfig(
        project_root=Path("C:/NetOps"),
        memory_mb=1024,
        cpus=2,
        snapshot=True,
    )

    command = virtual_desktop.build_qemu_command(
        config,
        Path("C:/QEMU/qemu-system-x86_64.exe"),
        Path("C:/NetOps/netops-os.qcow2"),
    )

    assert command[0].endswith("qemu-system-x86_64.exe")
    assert "-snapshot" in command
    assert "-m" in command and "1024" in command
    assert "-smp" in command and "2" in command
    assert any("format=qcow2" in item for item in command)
    assert all("&&" not in item and "|" not in item for item in command)


def test_build_qemu_command_uses_windows_safe_disk_path(monkeypatch) -> None:
    monkeypatch.setattr(
        virtual_desktop,
        "_short_windows_path",
        lambda path: r"C:\NETOAS~3\SLME~1\netops-os.qcow2",
    )
    config = virtual_desktop.VirtualDesktopConfig(project_root=Path("C:/NetOps"))

    command = virtual_desktop.build_qemu_command(
        config,
        Path("C:/QEMU/qemu-system-x86_64.exe"),
        Path("C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netops-os.qcow2"),
    )

    assert any("C:\\NETOAS~3\\SLME~1\\netops-os.qcow2" in item for item in command)


def test_manager_reports_missing_dependencies_without_spawning(tmp_path: Path) -> None:
    manager = virtual_desktop.VirtualDesktopManager(
        virtual_desktop.VirtualDesktopConfig(project_root=tmp_path),
        qemu_path=tmp_path / "missing-qemu.exe",
        disk_path=tmp_path / "missing-disk.qcow2",
    )

    result = manager.start()

    assert result["ok"] is False
    assert result["state"] == "unavailable"
    assert "bulunamad" in result["message"].casefold()


def test_find_disk_image_prefers_usable_installed_image_and_rejects_placeholder(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    placeholder = project_root / "netops_os" / "artifacts" / "netops-os.qcow2"
    placeholder.parent.mkdir(parents=True)
    placeholder.write_bytes(b"placeholder")

    installed = tmp_path / "NetOpsVM" / "netops-os.qcow2"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(virtual_desktop, "SYSTEM_DISK_IMAGE", installed)
    monkeypatch.setattr(virtual_desktop, "SYSTEM_BOOT_DISK_IMAGE", tmp_path / "missing-boot.vhdx")

    assert virtual_desktop.find_disk_image(project_root) == installed

    installed.unlink()
    assert virtual_desktop.find_disk_image(project_root) is None


def test_manager_reuses_running_process_and_only_stops_owned_process(tmp_path: Path) -> None:
    qemu = tmp_path / "qemu-system-x86_64.exe"
    disk = tmp_path / "netops-os.qcow2"
    qemu.write_bytes(b"qemu")
    disk.write_bytes(b"disk")
    manager = virtual_desktop.VirtualDesktopManager(
        virtual_desktop.VirtualDesktopConfig(project_root=tmp_path),
        qemu_path=qemu,
        disk_path=disk,
    )
    calls: list[tuple[list[str], dict]] = []

    class FakeProcess:
        pid = 1234

        def poll(self):
            return None

        def terminate(self):
            calls.append((["terminate"], {}))

        def wait(self, timeout=None):
            calls.append((["wait"], {"timeout": timeout}))
            return 0

        def kill(self):
            calls.append((["kill"], {}))

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    manager._popen = fake_popen
    first = manager.start()
    second = manager.start()
    stopped = manager.stop()

    assert first["ok"] is True
    assert second["state"] == "running"
    assert sum(1 for command, _ in calls if command and command[0] != "terminate" and command[0] != "wait") == 1
    assert stopped["state"] == "stopped"
    assert any(command == ["terminate"] for command, _ in calls)


def test_power_shell_launcher_matches_safe_defaults() -> None:
    script = (Path(__file__).resolve().parents[1] / "netops_os" / "scripts" / "run-qemu.ps1").read_text(
        encoding="utf-8"
    )

    assert "[int]$MemoryMB = 1024" in script
    assert "[int]$Cpus = 2" in script
    assert "[switch]$NoSnapshot" in script
    assert "if ($Snapshot -or -not $NoSnapshot)" in script


def test_power_shell_launcher_uses_a_file_path_for_configured_qemu() -> None:
    script = (Path(__file__).resolve().parents[1] / "netops_os" / "scripts" / "run-qemu.ps1").read_text(
        encoding="utf-8"
    )

    assert "$qemuPath =" in script
    assert "$qemu.FullName" in script
    assert "& $qemuPath @argsList" in script

