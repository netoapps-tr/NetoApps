from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def test_netops_setup_output_does_not_show_base_distribution_branding() -> None:
    build_script = (PROJECT / "netops_os" / "scripts" / "build-netops-preview.ps1").read_text(
        encoding="utf-8"
    )
    readme = (PROJECT / "netops_os" / "README.md").read_text(encoding="utf-8")

    assert "Debian 13 netinst indiriliyor" not in build_script
    assert "Debian tabanli NetOps OS kurulumu" not in build_script
    assert "Debian ISO SHA512" not in build_script
    assert "Debian-based preview" not in readme

    assert "NetOps OS kurulum imaji indiriliyor" in build_script
    assert "NetOps OS kurulumu QEMU icinde basliyor" in build_script


def test_installed_os_release_exposes_netops_identity() -> None:
    installer = (PROJECT / "netops_os" / "guest" / "install-netops-preview.sh").read_text(
        encoding="utf-8"
    )

    assert "cat > /etc/netops/os-release" in installer
    assert "rm -f /etc/os-release" in installer
    assert "ln -s /etc/netops/os-release /etc/os-release" in installer
    assert 'PRETTY_NAME="NetOps OS Preview"' in installer
