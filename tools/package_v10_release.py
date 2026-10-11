"""Build the small signed-by-digest driver bundle for a NetOps v10 release."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neto_version import APP_VERSION, RELEASE_REPOSITORY, RELEASE_TAG


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_driver(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(source, source.name)
    return sha256(destination)


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    components = {}
    for component, module in (
        ("visual_driver", "neto_visual_driver.py"),
        ("now_playing_driver", "neto_now_playing_driver.py"),
    ):
        asset = output / f"{component}-{APP_VERSION}.zip"
        digest = package_driver(ROOT / module, asset)
        components[component] = {
            "version": APP_VERSION,
            "module": module,
            "package": "zip",
            "asset_url": f"{RELEASE_REPOSITORY}/releases/download/{RELEASE_TAG}/{asset.name}",
            "sha256": digest,
            "notes": "NetOps v10.37.0 verified component driver",
        }
    manifest = {
        "manifest_version": "1",
        "app_min_version": APP_VERSION,
        "release": RELEASE_TAG,
        "components": components,
    }
    manifest_path = output / "netops_components.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Package NetOps v10 component drivers.")
    parser.add_argument("--output", type=Path, default=ROOT / "_github_release_v10.37.0")
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "components": manifest["components"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
