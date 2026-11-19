from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def test_xfce_session_and_netops_autostart_are_wired() -> None:
    preseed = (PROJECT / "netops_os" / "seed" / "preseed.cfg.template").read_text(encoding="utf-8")
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(encoding="utf-8")
    xfce_script = PROJECT / "netops_os" / "guest" / "configure-xfce-netops.sh"
    xfce = xfce_script.read_text(encoding="utf-8")

    assert "xfce4-whiskermenu-plugin" in preseed
    assert "xfce4-pulseaudio-plugin" in preseed
    assert "configure-xfce-netops.sh" in installer
    assert "autologin-session=netops" in installer
    assert "user-session=netops" in installer
    assert ".config/xfce4" in xfce
    assert "button_layout" in xfce
    assert "plugin-ids" in xfce
    assert "WALLPAPER=\"$WALLPAPER_DIR/debian-emerald.svg\"" in xfce
    assert "NETOPS_WALLPAPER_URL" in xfce


def test_xfce_customizer_keeps_debian_artwork_as_the_offline_fallback() -> None:
    xfce = (PROJECT / "netops_os" / "guest" / "configure-xfce-netops.sh").read_text(encoding="utf-8")

    assert "/usr/share/desktop-base" in xfce
    assert "emerald-theme" in xfce
    assert "curl" in xfce or "wget" in xfce


def test_preview_builder_is_pinned_to_debian_12_bookworm() -> None:
    build_script = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )
    preseed = (PROJECT / "netops_os" / "seed" / "preseed.cfg.template").read_text(encoding="utf-8")

    assert "$DebianVersion = '12.15.0'" in build_script
    assert "cdimage/archive/$DebianVersion" in build_script
    assert "mirror/suite string bookworm" in preseed
    assert "debian-13.7.0" not in build_script
    assert "d-i anna/no_kernel_modules boolean true" not in preseed
    assert "preseed/url=http://10.0.2.2:8000/preseed.cfg" in build_script
    assert "anna/no_kernel_modules=true" not in build_script
    assert "-device','e1000,netdev=net0'" in build_script
    assert "Copy-Item -LiteralPath (Join-Path $drive 'install.amd\\vmlinuz')" in build_script


def test_preview_builder_can_target_a_separate_disk_image() -> None:
    build_script = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$DiskImage = ''" in build_script
    assert "$disk = if ($DiskImage)" in build_script


def test_preview_builder_supports_whpx_acceleration() -> None:
    build_script = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )

    assert "[switch]$UseWHPX" in build_script
    assert "$accel = if ($UseWHPX)" in build_script
    assert "'-accel',$accel" in build_script


def test_preview_builder_keeps_new_disk_image_within_eight_gb() -> None:
    build_script = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )

    assert "qemuImg create -f qcow2 $disk 8G" in build_script


def test_qemu_runtime_forwards_remote_device_service_without_opening_a_guest_terminal() -> None:
    run_script = (PROJECT / "netops_os" / "scripts" / "run-qemu.ps1").read_text(encoding="utf-8")
    start_script = (PROJECT / "netops_os" / "scripts" / "start-netops-os.ps1").read_text(encoding="utf-8")

    assert "RemotePort = 9876" in run_script
    assert "hostfwd=tcp::${RemotePort}-:8765" in run_script
    assert "hostfwd=tcp::${remotePort}-:8765" in start_script


def test_qemu_runtime_prefers_the_legacy_under_8gb_xfce_image() -> None:
    run_script = (PROJECT / "netops_os" / "scripts" / "run-qemu.ps1").read_text(encoding="utf-8")

    assert "$legacyDisk = 'C:\\NetOpsVM\\netops-os-xfce-remote.qcow2'" in run_script
    assert "Test-Path -LiteralPath $legacyDisk" in run_script


def test_netops_guest_has_turkish_ui_and_shutdown_screen() -> None:
    app = (PROJECT / "netops_os" / "guest" / "netops_app.py").read_text(encoding="utf-8")

    assert 'self.root.protocol("WM_DELETE_WINDOW", self.shutdown)' in app
    assert "Kapanıyor..." in app
    assert "Sistem güvenli şekilde kapatılıyor." in app
    assert 'self.label(self.sidebar, "ÇALIŞMA ALANI"' in app
    assert 'self.label(self.sidebar, "SİSTEM"' in app
    assert 'text="Axvord hazır"' in app
    assert '"Native"' not in app
    assert "guest sürümünde" not in app


def test_netops_installer_copies_the_turkish_guest_app() -> None:
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(encoding="utf-8")

    assert "cp /tmp/netops-payload/netops_app.py /opt/netops/netops_app.py" in installer
    assert "autologin-session=netops" in installer
