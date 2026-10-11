from __future__ import annotations
import sys

ALIASES = {
    "force_fast": "force_fast",
    "zorla_hizli": "force_fast",
    "fast": "force_fast",
    "balanced": "balanced",
    "dengeli": "balanced",
    "full": "balanced",
    "custom": "balanced",
}

def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    profile = ALIASES.get(str(raw).strip().lower())
    if profile is None:
        print("Kullanim: python neto_profile_cli.py force_fast|balanced")
        return 2
    from neto_runtime_policy_v2 import set_profile, profile_label
    result = set_profile(profile)
    print(f"Profil ayarlandi: {profile_label(profile, 'tr')} ({profile})")
    print(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
