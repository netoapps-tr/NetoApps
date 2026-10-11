# NetOps security helpers
# Local-only API token, safe process/file helpers, safe calculator.

import ast
import os
import re
import secrets
import subprocess
from pathlib import Path

SAFE_PROCESS_RE = re.compile(r"^[A-Za-z0-9_. -]{1,80}(?:\.exe)?$", re.I)
SAFE_FILE_CHARS_RE = re.compile(r"[^A-Za-z0-9ğüşöçıİĞÜŞÖÇ_. -]+", re.I)


def appdata_dir():
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    path = Path(base) / "NetoAssistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_or_create_local_api_token():
    token_file = appdata_dir() / "local_api_token.txt"
    try:
        if token_file.exists():
            token = token_file.read_text(encoding="utf-8").strip()
            if len(token) >= 24:
                return token
        token = secrets.token_urlsafe(32)
        token_file.write_text(token, encoding="utf-8")
        return token
    except Exception:
        return secrets.token_urlsafe(32)


def is_loopback(addr):
    addr = str(addr or "")
    return addr in {"127.0.0.1", "::1", "localhost"} or addr.startswith("127.")


def sanitize_filename(name, fallback="Neto_Not"):
    name = str(name or "").strip().replace("/", "_").replace("\\", "_")
    name = SAFE_FILE_CHARS_RE.sub("_", name).strip(" ._")
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"}
    if not name or name.upper() in reserved:
        name = fallback
    return name[:80]


def safe_taskkill(process_name):
    process_name = str(process_name or "").strip()
    if not process_name.endswith(".exe"):
        process_name += ".exe"
    if not SAFE_PROCESS_RE.fullmatch(process_name):
        return False, "Güvenlik nedeniyle işlem adı reddedildi."
    try:
        completed = subprocess.run(
            ["taskkill", "/f", "/im", process_name],
            capture_output=True,
            text=True,
            timeout=8,
            shell=False,
        )
        return completed.returncode == 0, (completed.stdout or completed.stderr or "")[:600]
    except Exception as exc:
        return False, str(exc)


def safe_popen(args):
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
        return True
    except Exception:
        return False


_ALLOWED_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
_ALLOWED_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}


def _safe_eval_node(node):
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 8:
            raise ValueError("Üs çok büyük.")
        return _ALLOWED_BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError("Bu hesaplama güvenlik nedeniyle reddedildi.")


def safe_eval_math(expr):
    expr = str(expr or "").strip()
    if not expr:
        raise ValueError("Boş hesaplama.")
    if len(expr) > 120:
        raise ValueError("Hesaplama çok uzun.")
    if not re.fullmatch(r"[0-9+\-*/%().\s]+", expr):
        raise ValueError("Sadece matematik karakterleri kullanılabilir.")
    tree = ast.parse(expr, mode="eval")
    result = _safe_eval_node(tree)
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


def dangerous_command_words(text):
    k = str(text or "").lower()
    words = [
        "format", "wipe", "factory reset", "bootloader unlock", "fastboot flashing unlock",
        "rm -rf", "del /s", "reg delete", "cipher /w", "diskpart", "bcdedit",
    ]
    return [w for w in words if w in k]
