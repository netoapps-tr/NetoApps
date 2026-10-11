#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

project = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
pointer = project / "NETO_V27_SON_YEDEK.txt"
if not pointer.is_file():
    raise SystemExit("NETO_V27_SON_YEDEK.txt bulunamadı.")
backup = Path(pointer.read_text(encoding="utf-8").strip())
if not backup.is_dir():
    raise SystemExit(f"Yedek bulunamadı: {backup}")

restored = False
for name in ("asistan beta.py", "asistan_beta.py"):
    source = backup / name
    if source.is_file():
        shutil.copy2(source, project / name)
        print(f"Geri yüklendi: {name}")
        restored = True

if not restored:
    raise SystemExit("Yedekte asistan kaynak dosyası bulunamadı.")
print("SONUC: GERI ALMA BASARILI")
