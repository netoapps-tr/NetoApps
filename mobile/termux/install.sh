#!/data/data/com.termux/files/usr/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
TARGET_DIR="$PREFIX_DIR/lib/netops-shell"

command -v python >/dev/null 2>&1 || {
  printf '%s\n' 'Python bulunamadı. Önce: pkg install python'
  exit 1
}

mkdir -p "$TARGET_DIR" "$PREFIX_DIR/bin"
cp "$SCRIPT_DIR/netops_shell.py" "$TARGET_DIR/netops_shell.py"
cp "$SCRIPT_DIR/neto_termux_recovery_ui.py" "$TARGET_DIR/neto_termux_recovery_ui.py"
cp "$SCRIPT_DIR/netops" "$PREFIX_DIR/bin/netops"
chmod 700 "$TARGET_DIR/netops_shell.py" "$TARGET_DIR/neto_termux_recovery_ui.py" "$PREFIX_DIR/bin/netops"
python -m py_compile "$TARGET_DIR/netops_shell.py" "$TARGET_DIR/neto_termux_recovery_ui.py"
printf '%s\n' 'netops-shell kuruldu. Yardım için: netops --help'
