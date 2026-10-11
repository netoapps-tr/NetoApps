from __future__ import annotations

import concurrent.futures
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

RAW_URL = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
VERIFIED_URL = "https://raw.githubusercontent.com/hfcorriez/agent-public-apis/main/data/apis.json"
BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "neto_public_apis_catalog.json"
AUDIT_PATH = BASE_DIR / "neto_public_apis_audit.json"
VERIFIED_PATH = BASE_DIR / "neto_public_apis_verified.json"
VERIFIED_AUDIT_PATH = BASE_DIR / "neto_public_apis_verified_audit.json"
STATE_PATH = BASE_DIR / "neto_public_apis_audit_state.json"
HEALTH_PATH = BASE_DIR / "neto_public_apis_health.json"
SYNC_MAX_AGE = 24 * 3600
AUDIT_HEALTH_MAX_AGE = 7 * 24 * 3600

_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
_ROW_RE = re.compile(
    r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|?\s*$"
)


def _clean_auth(value: str) -> str:
    return str(value or "").replace("`", "").strip()


def parse_readme(text: str) -> list[dict[str, Any]]:
    category = ""
    entries: list[dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        m = _HEADING_RE.match(line)
        if m:
            category = m.group(1).strip()
            continue
        if not category or not line.startswith("| ["):
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        name, url, description, auth, https, cors = m.groups()
        # Skip non-directory tables such as APILayer promotional block.
        if category.lower().startswith("api") and "layer" in category.lower():
            continue
        entries.append({
            "name": name.strip(),
            "url": url.strip(),
            "description": re.sub(r"\s+", " ", description.strip()),
            "auth": _clean_auth(auth),
            "https": https.strip(),
            "cors": cors.strip(),
            "category": category,
        })
    return entries


def _download_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NetOps-One/10.39 public-apis-sync", "Accept": "text/plain,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def sync_catalog(force: bool = False) -> dict[str, Any]:
    if not force and CATALOG_PATH.exists():
        age = time.time() - CATALOG_PATH.stat().st_mtime
        if age < SYNC_MAX_AGE:
            return load_catalog(sync_if_missing=False)
    text = _download_text(RAW_URL)
    entries = parse_readme(text)
    payload = {
        "source": RAW_URL,
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "entry_count": len(entries),
        "entries": entries,
    }
    CATALOG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_catalog(sync_if_missing: bool = True) -> dict[str, Any]:
    if CATALOG_PATH.exists():
        try:
            data = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data
        except Exception:
            pass
    if sync_if_missing:
        try:
            return sync_catalog(force=True)
        except Exception:
            pass
    return {"source": RAW_URL, "synced_at": "", "entry_count": 0, "entries": []}



def sync_verified(force: bool = False) -> dict[str, Any]:
    if not force and VERIFIED_PATH.exists():
        age = time.time() - VERIFIED_PATH.stat().st_mtime
        if age < SYNC_MAX_AGE:
            return load_verified(sync_if_missing=False)
    raw = _download_text(VERIFIED_URL, timeout=20)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("apis"), list):
        raise ValueError("verified catalog invalid")
    # Keep only HTTPS endpoints. The source catalog is no-key/no-signup by design.
    apis = [a for a in data.get("apis", []) if str(a.get("url") or "").startswith("https://")]
    payload = {
        "source": VERIFIED_URL,
        "generated_at": data.get("generated_at"),
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(apis),
        "apis": apis,
    }
    VERIFIED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_verified(sync_if_missing: bool = True) -> dict[str, Any]:
    if VERIFIED_PATH.exists():
        try:
            data = json.loads(VERIFIED_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and isinstance(data.get("apis"), list):
                return data
        except Exception:
            pass
    if sync_if_missing:
        try:
            return sync_verified(force=True)
        except Exception:
            pass
    return {"source": VERIFIED_URL, "count": 0, "apis": []}



def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _file_is_fresh(path: Path, max_age: int = AUDIT_HEALTH_MAX_AGE) -> bool:
    try:
        return path.exists() and (time.time() - path.stat().st_mtime) <= max_age
    except Exception:
        return False


def _classify_verified_error(error: str) -> str:
    e = str(error or "")
    el = e.casefold()
    if "http error 404" in el or "http error 410" in el:
        return "dead"
    if "certificate_verify_failed" in el:
        return "unsafe_tls"
    if "http error 525" in el:
        return "tls_server_error"
    if any(x in el for x in ("http error 408", "http error 429", "http error 500", "http error 502",
                              "http error 503", "http error 504", "timeout", "timed out",
                              "winerror 10054", "remotedisconnected", "connection reset")):
        return "transient"
    return "failed"


def _verified_health_index() -> dict[tuple[str, str], dict[str, Any]]:
    """Latest known live health keyed by (id, url).

    Prefer the user's most recent full audit. The compact bundled health
    snapshot is only a seed until a fresh audit is run on this machine.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    audit = _load_json_file(VERIFIED_AUDIT_PATH)
    if audit and _file_is_fresh(VERIFIED_AUDIT_PATH):
        for row in audit.get("results") or []:
            api = row.get("api") or {}
            key = (str(api.get("id") or "").casefold(), str(api.get("url") or ""))
            if not key[0]:
                continue
            state = "ok" if row.get("ok") else _classify_verified_error(str(row.get("error") or ""))
            index[key] = {
                "state": state,
                "ok": bool(row.get("ok")),
                "latency_ms": row.get("latency_ms"),
                "error": row.get("error") or "",
                "checked_at": audit.get("checked_at") or "",
            }
        return index

    seed = _load_json_file(HEALTH_PATH)
    for row in ((seed.get("verified") or {}).get("endpoints") or []):
        key = (str(row.get("id") or "").casefold(), str(row.get("url") or ""))
        if key[0]:
            index[key] = dict(row)
    return index


def verified_health(api: dict[str, Any]) -> dict[str, Any]:
    idx = _verified_health_index()
    key = (str(api.get("id") or "").casefold(), str(api.get("url") or ""))
    item = idx.get(key)
    if item:
        return item
    aid = key[0]
    matches = [v for (i, _u), v in idx.items() if i == aid]
    if matches:
        matches.sort(key=lambda x: {"ok": 0, "dead": 1, "unsafe_tls": 2, "tls_server_error": 3, "transient": 4, "failed": 5}.get(str(x.get("state")), 9))
        return matches[0]
    return {"state": "unknown", "ok": None, "error": "", "latency_ms": None}


def _normalize_api_lookup(value: str) -> str:
    text = str(value or "").casefold().strip()
    table = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "’": "'", "`": "'",
    })
    text = text.translate(table)
    return re.sub(r"[^a-z0-9&+._-]+", "", text)


def _find_verified_api(name_or_id: str, apis: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Resolve a verified API without silently preferring loose substring matches.

    Order: exact id -> exact name -> normalized exact -> prefix -> substring.
    Health only breaks ties inside the same resolution class.
    """
    raw = str(name_or_id or "").strip()
    needle = raw.casefold()
    normalized = _normalize_api_lookup(raw)
    if not needle:
        return None
    apis = apis if apis is not None else (load_verified().get("apis") or [])

    def health_rank(api: dict[str, Any]) -> int:
        state = str(verified_health(api).get("state") or "unknown")
        return {"ok": 0, "unknown": 1, "transient": 2, "tls_server_error": 3, "failed": 4, "dead": 5, "unsafe_tls": 6}.get(state, 7)

    stages = [
        [a for a in apis if needle == str(a.get("id") or "").casefold()],
        [a for a in apis if needle == str(a.get("name") or "").casefold()],
        [a for a in apis if normalized and normalized in {
            _normalize_api_lookup(str(a.get("id") or "")),
            _normalize_api_lookup(str(a.get("name") or "")),
        }],
        [a for a in apis if normalized and (
            _normalize_api_lookup(str(a.get("id") or "")).startswith(normalized)
            or _normalize_api_lookup(str(a.get("name") or "")).startswith(normalized)
        )],
        [a for a in apis if normalized and normalized in _normalize_api_lookup(str(a.get("name") or ""))],
    ]
    for matches in stages:
        if matches:
            matches.sort(key=lambda a: (health_rank(a), len(str(a.get("name") or "")), str(a.get("name") or "").casefold()))
            return matches[0]
    return None


def resolve_verified(name_or_id: str) -> dict[str, Any] | None:
    """Public resolver used by Autopilot/Automation integrations."""
    return _find_verified_api(name_or_id)


def call_verified_exact(name_or_id: str, timeout: int = 8) -> dict[str, Any]:
    """Call the requested verified provider itself, with no fallback substitution.

    This is intentionally different from call_verified(): monitoring must be able
    to notice that the requested provider is down even when a fallback is healthy.
    """
    api = _find_verified_api(name_or_id)
    if not api:
        raise LookupError(f"verified API not found: {name_or_id}")
    health = verified_health(api)
    state = str(health.get("state") or "unknown")
    if state in {"dead", "unsafe_tls"}:
        return {
            "ok": False,
            "api": api,
            "error": f"known-unhealthy from recent audit ({state}): {health.get('error') or 'endpoint unavailable'}",
            "health_state": state,
            "latency_ms": health.get("latency_ms"),
        }
    result = _call_verified_api(
        api,
        timeout=timeout,
        attempts=2 if state in {"unknown", "transient", "tls_server_error", "failed"} else 1,
    )
    result["health_state"] = state
    return result


def _is_transient_exception(exc: Exception) -> bool:
    e = f"{type(exc).__name__}: {exc}".casefold()
    return any(x in e for x in (
        "timeout", "timed out", "http error 408", "http error 429",
        "http error 500", "http error 502", "http error 503", "http error 504",
        "winerror 10054", "remotedisconnected", "connection reset",
    ))


def _call_verified_api(api: dict[str, Any], timeout: int = 8, attempts: int = 2) -> dict[str, Any]:
    if api.get("spec_only"):
        return {"ok": False, "api": api, "error": "spec-only entry; no live data call performed"}
    url = str(api.get("url") or "")
    if not _safe_registered_https_url(url):
        return {"ok": False, "api": api, "error": "unsafe/non-HTTPS endpoint rejected"}

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NetOps-One/10.39 verified-public-api",
            "Accept": "application/json,text/plain,image/*,application/xml,text/xml,*/*",
        },
    )
    last_error = ""
    started_all = time.perf_counter()
    for attempt in range(max(1, int(attempts))):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read(1024 * 1024)
                status = int(getattr(response, "status", 200) or 200)
                ctype = str(response.headers.get("Content-Type") or "")
            elapsed = round((time.perf_counter() - started_all) * 1000)
            text_data = raw.decode("utf-8", errors="replace")
            try:
                body: Any = json.loads(text_data)
            except Exception:
                body = text_data[:20000]
            return {
                "ok": 200 <= status < 400,
                "api": api,
                "status": status,
                "latency_ms": elapsed,
                "content_type": ctype,
                "data": body,
                "attempts": attempt + 1,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < max(1, int(attempts)) and _is_transient_exception(exc):
                time.sleep(0.35 * (attempt + 1))
                continue
            break
    return {
        "ok": False,
        "api": api,
        "latency_ms": round((time.perf_counter() - started_all) * 1000),
        "error": last_error or "unknown error",
        "attempts": max(1, int(attempts)),
    }


def _fallback_api(api: dict[str, Any], apis: list[dict[str, Any]]) -> dict[str, Any] | None:
    fid = str(api.get("fallback") or "").strip()
    if not fid:
        return None
    return _find_verified_api(fid, apis)


def verified_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    apis = load_verified().get("apis") or []
    q = str(query or "").casefold().strip()
    if not q:
        ranked_all = sorted(apis, key=lambda a: (0 if verified_health(a).get("state") == "ok" else 1, str(a.get("category")), str(a.get("name"))))
        return ranked_all[:limit]
    words = [w for w in re.findall(r"[\w&+.-]+", q, re.UNICODE) if len(w) > 1]
    ranked = []
    for api in apis:
        name = str(api.get("name") or "")
        hay = " ".join(str(api.get(k) or "") for k in ("id", "name", "description", "category")).casefold()
        score = sum(4 if w in name.casefold() else 1 for w in words if w in hay)
        if score:
            health_penalty = 0 if verified_health(api).get("state") == "ok" else 1
            ranked.append((score, health_penalty, api))
    ranked.sort(key=lambda x: (-x[0], x[1], str(x[2].get("category")), str(x[2].get("name"))))
    return [x[2] for x in ranked[:limit]]


def _safe_registered_https_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        import ipaddress
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        host = parsed.hostname.casefold()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False


def call_verified(name_or_id: str, timeout: int = 8) -> dict[str, Any]:
    """Call a registered no-key endpoint with health-aware retry/fallback."""
    needle = str(name_or_id or "").casefold().strip()
    if not needle:
        raise ValueError("API name/id required")
    apis = load_verified().get("apis") or []
    api = _find_verified_api(needle, apis)
    if not api:
        raise LookupError(f"verified API not found: {name_or_id}")

    visited: set[tuple[str, str]] = set()
    primary = api
    primary_error = ""

    for _hop in range(4):
        key = (str(api.get("id") or "").casefold(), str(api.get("url") or ""))
        if key in visited:
            break
        visited.add(key)

        health = verified_health(api)
        state = str(health.get("state") or "unknown")
        if state in {"dead", "unsafe_tls"}:
            result = {
                "ok": False,
                "api": api,
                "error": f"known-unhealthy from recent audit ({state}): {health.get('error') or 'endpoint unavailable'}",
                "health_state": state,
            }
        else:
            result = _call_verified_api(
                api,
                timeout=timeout,
                attempts=2 if state in {"unknown", "transient", "tls_server_error", "failed"} else 1,
            )

        if result.get("ok"):
            if api is not primary:
                result["used_fallback"] = True
                result["primary_api"] = primary
                result["primary_error"] = primary_error
            result["health_state"] = verified_health(api).get("state") or "unknown"
            return result

        if not primary_error:
            primary_error = str(result.get("error") or "unknown error")

        fb = _fallback_api(api, apis)
        if not fb:
            if api is not primary:
                result["used_fallback"] = True
                result["primary_api"] = primary
                result["primary_error"] = primary_error
            return result
        api = fb

    return {
        "ok": False,
        "api": primary,
        "error": primary_error or "fallback chain exhausted",
        "fallback_chain_exhausted": True,
    }


def audit_verified(*, max_workers: int = 8, timeout: int = 6) -> dict[str, Any]:
    try:
        catalog = sync_verified(force=True)
    except Exception:
        catalog = load_verified(sync_if_missing=False)
    apis = [a for a in (catalog.get("apis") or []) if not a.get("spec_only")]
    results = []
    def probe(api):
        # Audit the exact row: the upstream catalog contains a few duplicate ids.
        return _call_verified_api(api, timeout=timeout, attempts=1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 10))) as pool:
        futures = [pool.submit(probe, api) for api in apis]
        for fut in concurrent.futures.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append({"ok": False, "error": str(exc)})
    payload = {
        "source": VERIFIED_URL,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    VERIFIED_AUDIT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload

def free_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Auth=No is the repository's strongest machine-readable signal that the API can
    # be called without credentials. User-Agent providers are also keyless.
    return [e for e in entries if str(e.get("auth") or "").strip().lower() in {"no", "user-agent"}]


def search_entries(query: str, *, only_free: bool = False, limit: int = 30) -> list[dict[str, Any]]:
    catalog = load_catalog()
    entries = catalog.get("entries") or []
    if only_free:
        entries = free_entries(entries)
    q = str(query or "").casefold().strip()
    if not q:
        return entries[:limit]
    words = [w for w in re.findall(r"[\w&+.-]+", q, re.UNICODE) if len(w) > 1]
    ranked = []
    for e in entries:
        hay = " ".join(str(e.get(k) or "") for k in ("name", "description", "category", "auth")).casefold()
        score = sum(3 if w in str(e.get("name") or "").casefold() else 1 for w in words if w in hay)
        if score:
            ranked.append((score, e))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("category")), str(item[1].get("name"))))
    return [e for _, e in ranked[:limit]]


def resolve_free_entry(name_or_id: str) -> dict[str, Any] | None:
    """Resolve a no-key/User-Agent entry from the public-apis README catalog."""
    raw = str(name_or_id or "").strip()
    if not raw:
        return None
    needle = raw.casefold()
    normalized = _normalize_api_lookup(raw)
    entries = free_entries(load_catalog().get("entries") or [])
    stages = [
        [e for e in entries if needle == str(e.get("name") or "").casefold()],
        [e for e in entries if normalized and normalized == _normalize_api_lookup(str(e.get("name") or ""))],
        [e for e in entries if normalized and _normalize_api_lookup(str(e.get("name") or "")).startswith(normalized)],
        [e for e in entries if normalized and normalized in _normalize_api_lookup(str(e.get("name") or ""))],
    ]
    for matches in stages:
        if matches:
            matches.sort(key=lambda e: (len(str(e.get("name") or "")), str(e.get("name") or "").casefold()))
            return matches[0]
    return None


def _probe_url(entry: dict[str, Any], timeout: int = 6) -> dict[str, Any]:
    url = str(entry.get("url") or "")
    started = time.perf_counter()
    status = None
    error = ""
    content_type = ""
    final_url = url
    # HEAD first, GET fallback. This verifies reachability of the listed resource,
    # not provider-specific API semantics.
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                method=method,
                headers={"User-Agent": "NetOps-One/10.39 public-apis-audit", "Accept": "application/json,text/html,*/*"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = int(getattr(response, "status", 200) or 200)
                content_type = str(response.headers.get("Content-Type") or "")
                final_url = str(response.geturl() or url)
                if method == "GET":
                    response.read(128)
            break
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if exc.code in (401, 403, 405) and method == "HEAD":
                continue
            error = f"HTTP {exc.code}"
            break
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if method == "HEAD":
                continue
            break
    elapsed = round((time.perf_counter() - started) * 1000)
    def _base_domain(value: str) -> str:
        try:
            host = (urlparse(value).hostname or "").casefold().strip(".")
            parts = host.split(".")
            return ".".join(parts[-2:]) if len(parts) >= 2 else host
        except Exception:
            return ""

    if status is not None and 200 <= status < 400:
        health = "ok"
    elif status == 404:
        health = "stale_404"
    elif status in (401, 403):
        health = "protected"
    elif status == 429:
        health = "rate_limited"
    elif status is not None and 400 <= status < 500:
        health = "client_error"
    elif status is not None and status >= 500:
        health = "server_error"
    elif "CERTIFICATE_VERIFY_FAILED" in error:
        health = "ssl_error"
    elif "timed out" in error.casefold():
        health = "timeout"
    elif "getaddrinfo" in error.casefold() or "name or service not known" in error.casefold():
        health = "dns_error"
    elif "10054" in error or "RemoteDisconnected" in error:
        health = "connection_error"
    else:
        health = "network_error"

    redirected_cross_domain = bool(
        final_url and final_url != url and _base_domain(url) and _base_domain(final_url)
        and _base_domain(url) != _base_domain(final_url)
    )
    return {
        **entry,
        "reachable": health == "ok",
        "network_reachable": status is not None and status < 500,
        "health": health,
        "status": status,
        "latency_ms": elapsed,
        "content_type": content_type,
        "final_url": final_url,
        "redirected_cross_domain": redirected_cross_domain,
        "error": error,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def probe_free_entry_exact(name_or_id: str, timeout: int = 8) -> dict[str, Any]:
    """Probe the exact no-key catalog resource with no fallback substitution."""
    entry = resolve_free_entry(name_or_id)
    if not entry:
        raise LookupError(f"free public API not found: {name_or_id}")
    result = _probe_url(entry, timeout=timeout)
    result["api"] = entry
    result["ok"] = (
        bool(result.get("reachable"))
        and str(result.get("health") or "") == "ok"
        and not bool(result.get("redirected_cross_domain"))
    )
    if result.get("redirected_cross_domain") and not result.get("error"):
        result["error"] = f"unsafe cross-domain redirect: {result.get('final_url') or ''}"
    return result


def _write_state(**kwargs: Any) -> None:
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            state = {}
    state.update(kwargs)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_all_free(*, max_workers: int = 8, timeout: int = 6) -> dict[str, Any]:
    try:
        catalog = sync_catalog(force=True)
    except Exception:
        catalog = load_catalog(sync_if_missing=False)
    entries = free_entries(catalog.get("entries") or [])
    _write_state(running=True, total=len(entries), done=0, started_at=time.strftime("%Y-%m-%d %H:%M:%S"), error="")
    results: list[dict[str, Any]] = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 12))) as pool:
        futures = [pool.submit(_probe_url, entry, timeout) for entry in entries]
        for fut in concurrent.futures.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append({"reachable": False, "error": str(exc)})
            done += 1
            if done == len(entries) or done % 10 == 0:
                _write_state(running=True, total=len(entries), done=done)
    results.sort(key=lambda e: (str(e.get("category")), str(e.get("name"))))
    health_counts: dict[str, int] = {}
    for item in results:
        key = str(item.get("health") or "unknown")
        health_counts[key] = health_counts.get(key, 0) + 1
    payload = {
        "source": RAW_URL,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "reachable": sum(1 for e in results if e.get("reachable")),
        "unreachable": sum(1 for e in results if not e.get("reachable")),
        "cross_domain_redirects": sum(1 for e in results if e.get("redirected_cross_domain")),
        "health_counts": health_counts,
        "note": "Listed URL health test; documentation/listing URLs are not equivalent to semantic API endpoint tests.",
        "results": results,
    }
    AUDIT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_state(running=False, total=len(entries), done=len(entries), finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    return payload


def start_audit_async() -> bool:
    state = audit_state()
    if state.get("running"):
        return False
    thread = threading.Thread(target=_audit_thread, name="netops-public-apis-audit", daemon=True)
    thread.start()
    return True


def _audit_thread() -> None:
    try:
        _write_state(running=True, phase="readme-links", error="")
        listed = audit_all_free()
        _write_state(
            running=True, phase="verified-endpoints",
            readme_total=listed.get("total", 0),
            readme_reachable=listed.get("reachable", 0),
        )
        verified = audit_verified()
        _write_state(
            running=False, phase="done",
            verified_total=verified.get("total", 0),
            verified_ok=verified.get("ok", 0),
            verified_failed=verified.get("failed", 0),
            finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        _write_state(running=False, error=f"{type(exc).__name__}: {exc}", finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))


def audit_state() -> dict[str, Any]:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {"running": False, "total": 0, "done": 0}


def _readme_health_map() -> dict[tuple[str, str], dict[str, Any]]:
    data = _load_json_file(AUDIT_PATH)
    mapping: dict[tuple[str, str], dict[str, Any]] = {}
    for row in data.get("results") or []:
        mapping[(str(row.get("name") or "").casefold(), str(row.get("url") or ""))] = row
    if not mapping:
        seed = _load_json_file(HEALTH_PATH)
        for row in ((seed.get("readme") or {}).get("entries") or []):
            mapping[(str(row.get("name") or "").casefold(), str(row.get("url") or ""))] = row
    return mapping


def _health_badge_for_entry(entry: dict[str, Any]) -> str:
    row = _readme_health_map().get((str(entry.get("name") or "").casefold(), str(entry.get("url") or "")))
    if not row:
        return "?"
    health = str(row.get("health") or "")
    if not health:
        status = row.get("status")
        if status is not None and 200 <= int(status) < 400:
            health = "ok"
        elif status == 404:
            health = "stale_404"
    if health == "ok":
        if row.get("redirected_cross_domain"):
            return "↪"
        return "✅"
    if health in {"protected", "rate_limited", "timeout", "network_error", "dns_error", "connection_error"}:
        return "⚠️"
    if health in {"stale_404", "server_error", "ssl_error", "client_error"}:
        return "❌"
    return "⚠️"


def format_query_answer(query: str) -> str | None:
    q = str(query or "").casefold()
    if not any(token in q for token in ("public-api", "public api", "publicapis", "public apis", "ücretsiz api", "ucretsiz api", "bedava api", "api katal")):
        return None
    if any(token in q for token in ("çağır", "cagir", "kullan")):
        cleaned_call = q
        for token in ("public-apis", "public api", "publicapis", "public apis", "api", "çağır", "cagir", "kullan"):
            cleaned_call = cleaned_call.replace(token, " ")
        cleaned_call = re.sub(r"\s+", " ", cleaned_call).strip()
        if not cleaned_call:
            return "Çağırmak istediğin doğrulanmış API adını yaz. Örnek: 'public api çağır Jikan'."
        result = call_verified(cleaned_call)
        api = result.get("api") or {}
        if not result.get("ok"):
            health = result.get("health_state") or "unknown"
            return f"{api.get('name') or cleaned_call} çağrısı başarısız [{health}]: {result.get('error') or 'bilinmeyen hata'}"
        data = result.get("data")
        preview = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        if result.get("used_fallback"):
            primary = result.get("primary_api") or {}
            return (
                f"{primary.get('name') or cleaned_call} yanıt vermedi; fallback olarak {api.get('name')} "
                f"({api.get('category')}) kullanıldı. HTTP {result.get('status')} / {result.get('latency_ms')} ms.\n"
                f"{preview[:2500]}"
            )
        return f"{api.get('name')} ({api.get('category')}) çağrıldı. HTTP {result.get('status')} / {result.get('latency_ms')} ms.\n{preview[:2500]}"
    if any(token in q for token in ("bozuklar", "başarısızlar", "basarisizlar", "ölüler", "oluler")):
        audit = _load_json_file(VERIFIED_AUDIT_PATH)
        if audit:
            bad = [r for r in (audit.get("results") or []) if not r.get("ok")]
            if not bad:
                return "Son doğrulanmış endpoint auditinde başarısız API yok."
            lines = [f"Son audit: {audit.get('ok', 0)}/{audit.get('total', 0)} başarılı. Başarısız kayıtlar:"]
            for row in bad[:30]:
                api = row.get("api") or {}
                state = _classify_verified_error(str(row.get("error") or ""))
                lines.append(f"• {api.get('name') or api.get('id')} [{state}] — {row.get('error')}")
            return "\n".join(lines)

        seed = _load_json_file(HEALTH_PATH)
        verified = seed.get("verified") or {}
        bad_seed = [r for r in (verified.get("endpoints") or []) if str(r.get("state") or "ok") != "ok"]
        if not bad_seed:
            return "Yerel audit raporu yok ve bundled sağlık snapshot'ında başarısız API bulunmuyor."
        lines = [f"Bundled sağlık snapshot'ı: {verified.get('ok', 0)}/{verified.get('total', 0)} başarılı. Sorunlu kayıtlar:"]
        for row in bad_seed[:30]:
            lines.append(f"• {row.get('name') or row.get('id')} [{row.get('state')}] — {row.get('error')}")
        return "\n".join(lines)

    if any(token in q for token in ("test et", "hepsini test", "audit başlat", "audit baslat")):
        started = start_audit_async()
        state = audit_state()
        if started:
            return "Public-APIs tam ücretsiz test turu arka planda başlatıldı: önce README'deki anahtarsız bağlantılar, ardından doğrulanmış canlı HTTPS endpointleri test edilecek. 'public api test durumu' yazarak ilerlemeyi görebilirsin."
        return f"Public-APIs testi zaten çalışıyor: {state.get('done', 0)}/{state.get('total', 0)} tamamlandı."
    if ("durum" in q and "test" in q) or any(token in q for token in ("api sağlık", "api saglik", "sağlık raporu", "saglik raporu")):
        state = audit_state()
        if state.get("running"):
            phase = state.get("phase") or "readme-links"
            if phase == "verified-endpoints":
                return f"Public-APIs testi sürüyor: README bağlantı turu tamamlandı; şimdi doğrulanmış canlı endpointler test ediliyor."
            return f"Public-APIs testi sürüyor: {state.get('done', 0)}/{state.get('total', 0)} README bağlantısı tamamlandı."
        if AUDIT_PATH.exists():
            try:
                data = json.loads(AUDIT_PATH.read_text(encoding="utf-8-sig"))
                base = f"Son README/listing sağlık testi: {data.get('reachable', 0)}/{data.get('total', 0)} sağlıklı, {data.get('unreachable', 0)} sorunlu."
                hc = data.get("health_counts") or {}
                if hc:
                    base += (
                        f" 404={hc.get('stale_404', 0)}, korumalı={hc.get('protected', 0)}, "
                        f"rate-limit={hc.get('rate_limited', 0)}, timeout={hc.get('timeout', 0)}, "
                        f"sunucu hatası={hc.get('server_error', 0)}."
                    )
                if VERIFIED_AUDIT_PATH.exists():
                    vd = json.loads(VERIFIED_AUDIT_PATH.read_text(encoding="utf-8-sig"))
                    base += f" Doğrulanmış endpoint testi: {vd.get('ok', 0)}/{vd.get('total', 0)} başarılı, {vd.get('failed', 0)} başarısız."
                return base
            except Exception:
                pass
        seed = _load_json_file(HEALTH_PATH)
        if seed:
            rd = seed.get("readme") or {}
            vd = seed.get("verified") or {}
            hc = rd.get("health_counts") or {}
            return (
                f"Bundled sağlık snapshot'ı: README/listing {hc.get('ok', 0)}/{rd.get('total', 0)} sağlıklı; "
                f"404={hc.get('stale_404', 0)}, timeout={hc.get('timeout', 0)}, DNS={hc.get('dns_error', 0)}. "
                f"Doğrulanmış endpointler: {vd.get('ok', 0)}/{vd.get('total', 0)} başarılı, {vd.get('failed', 0)} başarısız."
            )
        return "Henüz tamamlanmış bir Public-APIs testi yok."
    only_free = any(token in q for token in ("ücretsiz", "ucretsiz", "bedava", "anahtarsız", "anahtarsiz"))
    # Remove boilerplate words so category/name search is useful.
    cleaned = q
    for token in ("public-apis", "public api", "publicapis", "public apis", "ücretsiz", "ucretsiz", "bedava", "anahtarsız", "anahtarsiz", "api", "apiler", "listele", "bul", "göster", "goster"):
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    items = search_entries(cleaned, only_free=only_free, limit=20)
    catalog = load_catalog()
    all_entries = catalog.get("entries") or []
    free_count = len(free_entries(all_entries))
    if not items:
        return f"Public-APIs kataloğunda eşleşme bulamadım. Katalog: {len(all_entries)} giriş; anahtarsız/User-Agent: {free_count}."
    verified = load_verified().get("apis") or []
    lines = [f"Public-APIs kataloğu: {len(all_entries)} giriş, anahtarsız/User-Agent {free_count}; ayrıca çağrılabilir doğrulanmış HTTPS kataloğu: {len(verified)} endpoint."]
    for e in items:
        badge = _health_badge_for_entry(e)
        lines.append(f"• {badge} [{e.get('category')}] {e.get('name')} — {e.get('description')} (Auth: {e.get('auth')}, HTTPS: {e.get('https')})")
    if len(items) >= 20:
        lines.append("İlk 20 eşleşme gösterildi; kategori veya ad yazarak daraltabilirsin.")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NetOps public-apis catalog sync/audit")
    parser.add_argument("command", choices=["sync", "sync-verified", "audit", "audit-verified", "stats"])
    args = parser.parse_args()
    if args.command == "sync":
        data = sync_catalog(force=True)
        print(json.dumps({"entries": data.get("entry_count"), "path": str(CATALOG_PATH)}, ensure_ascii=False))
    elif args.command == "sync-verified":
        data = sync_verified(force=True)
        print(json.dumps({"verified": data.get("count"), "path": str(VERIFIED_PATH)}, ensure_ascii=False))
    elif args.command == "audit":
        data = audit_all_free()
        print(json.dumps({"total": data.get("total"), "reachable": data.get("reachable"), "unreachable": data.get("unreachable"), "path": str(AUDIT_PATH)}, ensure_ascii=False))
    elif args.command == "audit-verified":
        data = audit_verified()
        print(json.dumps({"total": data.get("total"), "ok": data.get("ok"), "failed": data.get("failed"), "path": str(VERIFIED_AUDIT_PATH)}, ensure_ascii=False))
    else:
        data = load_catalog()
        entries = data.get("entries") or []
        verified = load_verified(sync_if_missing=False).get("apis") or []
        print(json.dumps({"entries": len(entries), "free_keyless": len(free_entries(entries)), "verified_https": len(verified), "synced_at": data.get("synced_at")}, ensure_ascii=False))
