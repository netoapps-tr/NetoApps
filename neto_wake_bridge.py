"""LAN-only NetOps wake bridge.

The bridge is intentionally smaller and safer than the main application:
it exposes one authenticated wake endpoint, serves a phone voice page, and
starts or wakes NetOps. It never accepts arbitrary commands from the phone.
"""

from __future__ import annotations

import html
import hmac
import http.server
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen


BRIDGE_HOST = os.environ.get("NETO_WAKE_BIND", "0.0.0.0")
BRIDGE_PORT = int(os.environ.get("NETO_WAKE_PORT", "8765"))
APP_PORT = int(os.environ.get("NETO_LOCAL_API_PORT", "5000"))
STARTUP_VALUE_NAME = "NetOpsWakeBridge"
PUBLIC_TOKEN_NAME = "public_wake_token.txt"
_wake_lock = threading.Lock()
_last_wake = 0.0


def _appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "NetoAssistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token_path() -> Path:
    return _appdata_dir() / "local_api_token.txt"




def _public_token_path() -> Path:
    return _appdata_dir() / PUBLIC_TOKEN_NAME

def _get_token() -> str:
    try:
        token = _token_path().read_text(encoding="utf-8").strip()
        if len(token) >= 24:
            return token
    except Exception:
        pass
    try:
        import secrets

        token = secrets.token_urlsafe(32)
        _token_path().write_text(token, encoding="utf-8")
        return token
    except Exception:
        return "netops-local-wake-token"


def _get_public_token() -> str:
    """Return a separate least-privilege token for public wake requests."""
    try:
        token = _public_token_path().read_text(encoding="utf-8").strip()
        if len(token) >= 24:
            return token
    except Exception:
        pass
    try:
        import secrets

        token = secrets.token_urlsafe(32)
        _public_token_path().write_text(token, encoding="utf-8")
        return token
    except Exception:
        return "netops-public-wake-token"


def _bridge_script_path() -> Path:
    return Path(__file__).resolve()


def _app_script_path() -> Path:
    return _bridge_script_path().with_name("asistan beta.py")


def _app_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return _app_script_path()


def _app_command(*extra: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(sys.executable), *extra]
    return [sys.executable, str(_app_script_path()), *extra]


def _detached_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200))


def _local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        addresses.add(socket.gethostbyname(socket.gethostname()))
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        sock.connect(("192.0.2.1", 80))
        addresses.add(sock.getsockname()[0])
        sock.close()
    except Exception:
        pass
    result = []
    for address in sorted(addresses):
        try:
            ip = ipaddress.ip_address(address)
            if ip.version == 4 and not ip.is_loopback:
                result.append(address)
        except ValueError:
            continue
    return result or ["127.0.0.1"]


def _is_private_client(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False


def _process_is_running() -> bool:
    """Find the real app without confusing the bridge with the app."""
    try:
        import psutil

        app_path = str(_app_path()).lower()
        for process in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if process.pid == os.getpid():
                    continue
                command_line = " ".join(process.info.get("cmdline") or []).lower()
                if "--neto-wake-bridge" in command_line or "--neto-install-wake" in command_line:
                    continue
                executable = str(process.info.get("exe") or "").lower()
                is_bridge_process = "--neto-wake-bridge" in command_line or "--neto-install-wake" in command_line
                process_name = str(process.info.get("name") or "").lower()
                is_known_neto_process = process_name in {"netops.exe", "neto asistan.exe", "netoasistan.exe"} or Path(executable).name.lower() in {"netops.exe", "neto asistan.exe", "netoasistan.exe"}
                if executable and executable == app_path and not is_bridge_process:
                    return True
                if not is_bridge_process and ("asistan beta.py" in command_line or is_known_neto_process):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False


def _forward_to_running_app() -> bool:
    request = Request(
        f"http://127.0.0.1:{APP_PORT}/uyandir",
        headers={"X-Neto-Token": _get_token(), "User-Agent": "NetOpsWakeBridge/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=1.6) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def wake_netops() -> dict[str, object]:
    global _last_wake
    with _wake_lock:
        now = time.monotonic()
        if now - _last_wake < 2.0:
            return {"ok": True, "status": "cooldown", "message": "NetOps zaten uyandırılıyor."}
        _last_wake = now

        # Forward first. This closes the startup race where the UI process exists
        # but its local Flask endpoint is still becoming ready.
        if _forward_to_running_app():
            return {"ok": True, "status": "woken", "message": "NetOps zaten açıktı ve uyandırıldı."}
        if _process_is_running():
            return {"ok": True, "status": "already-running", "message": "NetOps açık; hazır olduğunda yanıt verecek."}

        try:
            subprocess.Popen(
                _app_command("--neto-wake"),
                cwd=str(_app_path().parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_detached_flags(),
                close_fds=os.name != "nt",
            )
            return {"ok": True, "status": "started", "message": "NetOps kapalıydı; otomatik açılıyor."}
        except Exception as exc:
            return {"ok": False, "status": "error", "message": f"NetOps açılamadı: {exc}"}


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --neto-wake-bridge'
    return f'"{sys.executable}" "{_bridge_script_path()}" --neto-wake-bridge'


def install_startup(start_now: bool = True) -> int:
    if os.name != "nt":
        print("Windows başlangıç kaydı yalnızca Windows'ta kullanılabilir.")
        return 2
    import winreg

    command = _startup_command()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, command)
    print("NetOps Wake Bridge başlangıca eklendi.")
    print(f"Komut: {command}")
    if start_now:
        subprocess.Popen(
            _app_command("--neto-wake-bridge"),
            cwd=str(_app_path().parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_detached_flags(),
            close_fds=os.name != "nt",
        )
    print_connection_info()
    return 0


def remove_startup() -> int:
    if os.name != "nt":
        return 2
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, STARTUP_VALUE_NAME)
        print("NetOps Wake Bridge başlangıçtan kaldırıldı.")
    except FileNotFoundError:
        print("NetOps Wake Bridge başlangıçta kayıtlı değildi.")
    return 0


def print_connection_info() -> None:
    token = quote(_get_public_token(), safe="")
    print(f"Port: {BRIDGE_PORT}")
    for address in _local_ipv4_addresses():
        print(f"Telefon bağlantısı: http://{address}:{BRIDGE_PORT}/#token={token}")
    print("Not: 162.x.x.x adresi yerel ağ adresi değildir. Router üzerinden 192.168.1.162 gibi sabit bir adres atanabilir.")


def _phone_page() -> bytes:
    document = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetOps Uyandırıcı</title>
<style>
body{{margin:0;background:#0d0f14;color:#f2f5ff;font:16px system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}}
main{{width:min(92vw,430px);background:#171b25;border:1px solid #2c3853;border-radius:24px;padding:28px;box-sizing:border-box;box-shadow:0 18px 50px #0008}}
h1{{margin:0 0 8px;color:#6b8cff}} p{{color:#aeb8ce;line-height:1.5}}
button{{width:100%;border:0;border-radius:16px;padding:16px;background:#4f6bff;color:white;font-size:17px;font-weight:700;cursor:pointer}}
button.wake{{background:#20c96b;margin-bottom:10px}}
button.stop{{background:#283149}} #state{{margin-top:18px;padding:12px;border-radius:12px;background:#10131b;color:#89ffa9}}
</style></head><body><main><h1>NetOps</h1>
<p>Ses tanıma destekleniyorsa “Hey Neto” dediğinde, desteklenmiyorsa aşağıdaki düğmeye dokunduğunda bilgisayardaki NetOps otomatik uyanır.</p>
<button id="wake" class="wake">Neto'yu Uyandır</button>
<button id="toggle">Dinlemeyi başlat</button><div id="state">Hazır</div>
<p style="font-size:13px">Bu sayfa yerel ağ veya güvenli Cloudflare Tunnel üzerinden NetOps'a bağlanır.</p></main>
<script>
const TOKEN={json.dumps(_get_public_token())}; let recognition=null; let listening=false; let restartAttempts=0; let restartTimer=null;
const state=document.getElementById('state'), wakeButton=document.getElementById('wake'), toggle=document.getElementById('toggle');
function say(text, ok=false){{state.textContent=text; state.style.color=ok?'#89ffa9':'#ffd479';}}
async function wake(){{if(!TOKEN){{say("Bu bağlantıda güvenlik anahtarı yok.");return;}}wakeButton.disabled=true;say('NetOps uyandırılıyor...','true');try{{const r=await fetch('/uyandir',{{method:'GET',headers:{{'X-Neto-Token':TOKEN}},cache:'no-store'}}); const d=await r.json(); say(d.message||'NetOps uyandırıldı.',!!d.ok);}}catch(e){{say('Bilgisayara ulaşılamadı. Ağ bağlantısını kontrol et.');}}finally{{setTimeout(()=>wakeButton.disabled=false,1200);}}}}
function resetListenUi(message){{listening=false;if(restartTimer){{clearTimeout(restartTimer);restartTimer=null;}}toggle.textContent='Dinlemeyi başlat';toggle.classList.remove('stop');if(message)say(message);}}
function start(){{const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R){{say('Bu tarayıcı ses tanımıyor. Yeşil düğmeye dokunarak uyandırabilirsin.');return;}}if(listening)return;restartAttempts=0;recognition=new R();recognition.lang='tr-TR';recognition.continuous=false;recognition.interimResults=false;recognition.maxAlternatives=3;
recognition.onstart=()=>say('Dinliyorum: “Hey Neto”');recognition.onerror=e=>{{if(!listening)return;if(e.error==='aborted'){{resetListenUi('Mikrofon oturumu kapandı. Tekrar denemek için düğmeye dokun.');return;}}if(e.error==='no-speech'){{say('Ses algılanmadı, tekrar dinliyorum...');return;}}resetListenUi('Mikrofon: '+e.error);}};recognition.onend=()=>{{if(!listening)return;if(restartAttempts<1){{restartAttempts++;say('Mikrofon yeniden deneniyor...');restartTimer=window.setTimeout(()=>{{try{{if(listening)recognition.start();}}catch(e){{resetListenUi('Mikrofon başlatılamadı. Tekrar denemek için düğmeye dokun.');}}}},500);}}else{{resetListenUi('Mikrofon bu tarayıcıda kullanılamadı. Düğmeye tekrar dokun.');}}}};
recognition.onresult=e=>{{for(let i=e.resultIndex;i<e.results.length;i++){{if(!e.results[i].isFinal)continue;const t=e.results[i][0].transcript.toLocaleLowerCase('tr-TR').replace(/[ıİ]/g,'i').replaceAll(' ','');if(t.includes('heyneto')||t.includes('heinet')||t.includes('heynet')||t.includes('heynato')){{say('Neto uyandırılıyor...',true);wake();}}}}}};
try{{listening=true;recognition.start();toggle.textContent='Dinlemeyi durdur';toggle.classList.add('stop');}}catch(e){{resetListenUi('Mikrofon başlatılamadı.');}}}}
function stop(){{try{{recognition&&recognition.stop();}}catch(e){{}}resetListenUi('Dinleme durdu.');}}
toggle.onclick=()=>listening?stop():start();
wakeButton.onclick=()=>wake();
</script></body></html>"""
    return document.encode("utf-8")


class _WakeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "NetOpsWakeBridge/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _query_token(self) -> str:
        query = parse_qs(urlsplit(self.path).query)
        return str((query.get("token") or [""])[0])

    def _authorized(self, public: bool = False) -> bool:
        supplied = self.headers.get("X-Neto-Token") or self._query_token()
        valid_tokens = [_get_token()]
        if public:
            valid_tokens.append(_get_public_token())
        return any(hmac.compare_digest(str(supplied), token) for token in valid_tokens)


    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not _is_private_client(self.client_address[0]):
            self._send(403, b'{"ok":false,"message":"Yerel ag erisimi gerekli."}')
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, _phone_page(), "text/html; charset=utf-8")
            return
        if path == "/uyandir" and self._authorized(public=True):
            result = wake_netops()
            self._send(200 if result.get("ok") else 500, json.dumps(result, ensure_ascii=False).encode())
            return
        if path == "/health" and self._authorized():
            self._send(200, json.dumps({"ok": True, "service": "NetOps Wake Bridge"}, ensure_ascii=False).encode())
            return
        self._send(401 if path in {"/", "/health", "/uyandir"} else 404, b'{"ok":false,"message":"Yetkisiz veya gecersiz istek."}')

    def do_POST(self) -> None:
        if not _is_private_client(self.client_address[0]) or not self._authorized(public=True):
            self._send(401, b'{"ok":false,"message":"Yetkisiz istek."}')
            return
        if urlsplit(self.path).path != "/uyandir":
            self._send(404, b'{"ok":false,"message":"Gecersiz endpoint."}')
            return
        result = wake_netops()
        self._send(200 if result.get("ok") else 500, json.dumps(result, ensure_ascii=False).encode())


def serve() -> int:
    try:
        server = http.server.ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), _WakeHandler)
    except OSError as exc:
        print(f"NetOps Wake Bridge baslatilamadi: {exc}")
        return 1
    print("NetOps Wake Bridge aktif.")
    print_connection_info()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--install-startup" in args:
        return install_startup(start_now=True)
    if "--remove-startup" in args:
        return remove_startup()
    if "--print-info" in args:
        print_connection_info()
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())








