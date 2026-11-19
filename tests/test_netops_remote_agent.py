from pathlib import Path

from netops_os.guest import netops_remote_agent


PROJECT = Path(__file__).resolve().parents[1]


def test_remote_agent_allows_named_system_operations_only() -> None:
    result = netops_remote_agent.dispatch_command("status", {})

    assert result["ok"] is True
    assert result["data"]["name"] == "NetOps OS"
    assert result["data"]["core"] == "Axvord"

    blocked = netops_remote_agent.dispatch_command("shell", {"command": "rm -rf /"})
    assert blocked == {"ok": False, "error": "UNKNOWN_COMMAND"}


def test_remote_agent_requires_confirmation_for_power_operations() -> None:
    assert netops_remote_agent.dispatch_command("poweroff", {}) == {
        "ok": False,
        "error": "CONFIRMATION_REQUIRED",
    }
    assert netops_remote_agent.dispatch_command("reboot", {}) == {
        "ok": False,
        "error": "CONFIRMATION_REQUIRED",
    }


def test_remote_agent_exposes_turkish_command_catalog() -> None:
    result = netops_remote_agent.dispatch_command("commands", {})

    assert result["ok"] is True
    assert "status" in result["commands"]
    assert "yeniden başlat" in result["commands"]["reboot"]
    assert "keyfi" in result["policy"]


def test_remote_service_is_installed_and_startup_desktop_does_not_open_terminal() -> None:
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(encoding="utf-8")
    service = (PROJECT / "netops_os" / "guest" / "netops-remote-agent.service").read_text(encoding="utf-8")
    session = (PROJECT / "netops_os" / "guest" / "netops-os-session.desktop").read_text(encoding="utf-8")
    autostart = (PROJECT / "netops_os" / "guest" / "netops-shell.desktop").read_text(encoding="utf-8")

    assert "netops_remote_agent.py" in installer
    assert "netops-remote-agent.service" in installer
    assert "systemctl enable" in installer and "netops-remote-agent.service" in installer
    assert "Terminal=false" in session
    assert "Terminal=false" in autostart
    assert "ExecStart=/usr/bin/python3 /opt/netops/netops_remote_agent.py" in service


def test_netops_session_is_the_graphical_autologin_target() -> None:
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(encoding="utf-8")

    assert "autologin-session=netops" in installer
    assert "user-session=netops" in installer
    assert "autologin-session=xfce" not in installer
    assert "user-session=xfce" not in installer


def test_netops_ui_can_show_remote_pairing_details() -> None:
    app = (PROJECT / "netops_os" / "guest" / "netops_app.py").read_text(encoding="utf-8")
    bridge = (PROJECT / "netops_os" / "guest" / "netops-system-agent.py").read_text(encoding="utf-8")

    assert 'bridge("remote_pairing")' in app
    assert 'action == "remote_pairing"' in bridge
