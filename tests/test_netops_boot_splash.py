from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def test_plymouth_theme_has_black_background_and_real_boot_progress() -> None:
    theme = (PROJECT / "netops_os" / "guest" / "netops.script").read_text(encoding="utf-8")

    assert "Window.SetBackgroundTopColor(0.0, 0.0, 0.0);" in theme
    assert "Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);" in theme
    assert "Plymouth.SetBootProgressFunction" in theme
    assert "Image.Text" in theme
    assert "progress" in theme


def test_guest_install_cleans_only_caches_and_temp_payload() -> None:
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(
        encoding="utf-8"
    )

    assert "apt-get clean" in installer
    assert "/var/lib/apt/lists/*" in installer
    assert "/var/cache/apt/*" in installer
    assert "/tmp/netops-payload" in installer
    assert "/usr/share/doc" not in installer


def test_preseed_keeps_netops_as_the_installed_session() -> None:
    preseed = (PROJECT / "netops_os" / "seed" / "preseed.cfg.template").read_text(
        encoding="utf-8"
    )

    assert "autologin-session=netops" in preseed
    assert "user-session=netops" in preseed
    assert "autologin-session=xfce" not in preseed


def test_installer_builder_keeps_the_original_qemu_display_behavior() -> None:
    builder = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )

    assert "-display','none'" not in builder
    assert "NetOps OS kurulumu QEMU icinde basliyor" in builder


def test_installer_builder_shows_netops_splash_before_debian_installer() -> None:
    builder = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )

    assert "netops-splash.bmp" in builder
    assert "netops-installer-splash.bmp" in builder
    assert "splash-time=2500" in builder


def test_normal_runtime_still_uses_the_guest_display() -> None:
    runner = (PROJECT / "netops_os" / "scripts" / "run-qemu.ps1").read_text(encoding="utf-8")

    assert "'-display', $display" in runner
    assert "'sdl'" in runner
    assert "Set-NetOpsSurfaceFullscreen" in runner
    assert "Start-Process" in runner
    assert "ShowQemuChrome" in runner
    assert "splash-time=5000" in runner


def test_guest_packages_keep_the_original_xfce_desktop_dependencies() -> None:
    preseed = (PROJECT / "netops_os" / "seed" / "preseed.cfg.template").read_text(
        encoding="utf-8"
    )
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(
        encoding="utf-8"
    )

    assert "firefox-esr" not in preseed
    assert "chromium" not in preseed
    assert "xfce4-clipman-plugin" in preseed
    assert "xfce4-indicator-plugin" not in preseed
    assert "xfce4-taskmanager" not in preseed
    assert "desktop-base" in preseed
    assert "xfce4-pulseaudio-plugin" in preseed
    assert "xfce4-whiskermenu-plugin" in preseed
    assert "curl" not in preseed
    assert "wget" in preseed
    assert "DuckDuckGo" not in installer
