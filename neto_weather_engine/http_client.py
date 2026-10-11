import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .cache import JsonCache


class HttpClient:
    def __init__(self, cache=None, user_agent=None):
        self.cache = cache or JsonCache()
        # MET Norway requires an identifiable User-Agent. Replace the URL with the
        # project's real public page if/when one is published.
        self.user_agent = user_agent or "NetOps-One/10.39 weather-engine"

    def get_json(self, url, params=None, timeout=8, ttl_seconds=600, headers=None, retries=2):
        params = params or {}
        full_url = url
        if params:
            full_url = url + "?" + urllib.parse.urlencode(params, doseq=True)
        cache_key = self.cache.key({"url": url, "params": params})
        cached = self.cache.get(cache_key, ttl_seconds)
        if cached is not None:
            return cached

        request_headers = {
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": self.user_agent,
        }
        if headers:
            request_headers.update(headers)

        last_error = None
        for attempt in range(max(0, int(retries)) + 1):
            req = urllib.request.Request(full_url, headers=request_headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = getattr(response, "status", None)
                    raw = response.read().decode("utf-8", errors="replace")
                # Several public weather APIs (notably AviationWeather) use
                # HTTP 204 / an empty body for a valid query with no data.
                # Treat that as an empty result instead of raising JSONDecodeError.
                if status == 204 or not raw.strip():
                    data = None
                else:
                    data = json.loads(raw)
                self.cache.set(cache_key, data)
                return data
            except urllib.error.HTTPError as exc:
                last_error = exc
                should_retry = exc.code == 429 or 500 <= exc.code <= 599
                if not should_retry or attempt >= retries:
                    break
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = min(float(retry_after), 15.0) if retry_after else (0.75 * (2 ** attempt))
                except Exception:
                    delay = 0.75 * (2 ** attempt)
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(0.5 * (2 ** attempt))

        stale = self.cache.get_stale(cache_key, max_age_seconds=max(86400, ttl_seconds * 12))
        if stale is not None:
            return stale
        if last_error:
            raise last_error
        raise RuntimeError("HTTP request failed")
