"""Create the 1.42 file-level update manifest for GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neto_version import APP_VERSION, RELEASE_REPOSITORY, RELEASE_TAG

SYSTEM_FILES = (
    "asistan beta.py",
    "neto_settings_page.py",
    "neto_updater.py",
    "neto_update_helper.py",
    "neto_system_updater.py",
    "neto_motion_engine_v2.py",
    "neto_runtime_core.py",
    "neto_version.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output: Path) -> dict:
    files = []
    for relative in SYSTEM_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        files.append(
            {
                "path": relative.replace("\\", "/"),
                "url": f"{RELEASE_REPOSITORY}/raw/{RELEASE_TAG}/{quote(relative)}",
                "sha256": sha256(source),
            }
        )
    manifest = {
        "manifest_version": "1",
        "version": APP_VERSION,
        "release_tag": RELEASE_TAG,
        "notes": "NetOps system-file update; full program download is not required.",
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the NetOps file-level update manifest.")
    parser.add_argument("--output", type=Path, default=ROOT / "netops_system_manifest.json")
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "files": len(manifest["files"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
