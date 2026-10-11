from dataclasses import dataclass, field


@dataclass
class ProviderResult:
    provider: str
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=None):
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except Exception:
        return default
