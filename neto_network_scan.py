"""NetOps LAN tarayıcı ve cihaz envanteri (v1.40 eklentisi).

Bu modül SADECE EKLEME amaçlıdır. Mevcut modüllerin hiçbir davranışını
değiştirmez, hiçbir dosyayı silmez. Kendi verisini kendi klasöründe tutar.

Tasarım ilkeleri
----------------
* Varsayılan PASİF: yalnızca işletim sisteminin ARP/komşu tablosu okunur.
  Hiçbir paket gönderilmez.
* Aktif tarama yalnızca açık komutla ve yalnızca yerel özel alt ağda yapılır.
* Sınırlı: en fazla /24, sabit eşzamanlılık, kısa zaman aşımı, toplam süre bütçesi.
* Sömürü, parola denemesi, zafiyet taraması, paket yakalama YOKTUR.
* Port taraması isteğe bağlıdır ve yaygın portlarla sınırlıdır.
* Veriler yerel diske yazılır; dışarı gönderilmez. Tek istisna: MAC üretici
  sorgusu, o da yalnızca kullanıcı açıkça isterse ve sonucu önbelleğe alınır.

Yasal not: Bu aracı yalnızca sahibi olduğunuz veya açık izin aldığınız ağlarda
kullanın. Başkasının ağında tarama yapmak bulunduğunuz ülkede suç olabilir.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

__all__ = [
    "scan",
    "passive_devices",
    "format_report",
    "handle_command",
    "network_scan_ac",
    "load_inventory",
    "inventory_summary",
]

# ----------------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------------

APP_FOLDER = "NetoAssistant"
SUBFOLDER = "network_scan"
INVENTORY_FILE = "inventory.json"
VENDOR_CACHE_FILE = "vendor_cache.json"

# Tarama sınırları (güvenlik ve hız dengesi)
MAX_HOSTS = 254          # en fazla /24
SWEEP_WORKERS = 128      # eşzamanlı ping sayısı (yalnızca derin taramada)
PING_TIMEOUT_MS = 500    # tek ping bekleme süresi
HOST_TIMEOUT_S = 1.6     # ping alt süreci için üst sınır
SCAN_BUDGET_S = 20.0     # toplam tarama bütçesi (aşılırsa kalan atlanır)
PRIME_WAIT_S = 0.9       # ARP yoklaması sonrası tablonun oturması için bekleme

# Yaygın portlar (isteğe bağlı derin tarama)
COMMON_PORTS = (22, 80, 135, 139, 443, 445, 554, 631, 3389, 5000, 8080, 8443, 9100)
PORT_TIMEOUT_S = 0.45

# ARP tablosunda gösterilmemesi gereken adresler
_SKIP_NETS = (
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("239.0.0.0/8"),
    ipaddress.ip_network("255.255.255.255/32"),
)

_ARP_ROW_RE = re.compile(
    r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"(?P<mac>[0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})"
)

_lock = threading.RLock()
_window_ref: Any = None


# ----------------------------------------------------------------------------
# Yollar
# ----------------------------------------------------------------------------

def _base_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_FOLDER / SUBFOLDER


def _ensure_dir() -> Path:
    path = _base_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def _inventory_path() -> Path:
    return _ensure_dir() / INVENTORY_FILE


def _vendor_cache_path() -> Path:
    return _ensure_dir() / VENDOR_CACHE_FILE


def _no_window_flag() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ----------------------------------------------------------------------------
# Ağ bilgisi
# ----------------------------------------------------------------------------

def local_ipv4() -> str:
    """Yerel IPv4 adresini döndürür (paket göndermeden)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(0.5)
            # 192.0.2.1 (TEST-NET-1) yalnızca yerel arayüz seçimi için kullanılır,
            # gerçek bir bağlantı kurulmaz.
            sock.connect(("192.0.2.1", 80))
            return str(sock.getsockname()[0])
        finally:
            sock.close()
    except Exception:
        pass
    try:
        return str(socket.gethostbyname(socket.gethostname()))
    except Exception:
        return "127.0.0.1"


def local_subnet() -> tuple[str, int]:
    """(ağ adresi, prefix) döndürür. Bilinemezse /24 varsayılır."""
    ip = local_ipv4()
    try:
        iface = ipaddress.ip_address(ip)
        if iface.is_loopback:
            return ("127.0.0.0", 8)
        # Netmask öğrenilemezse /24 kabul et (ev/ofis ağlarının çoğu).
        return (str(ipaddress.ip_network(f"{ip}/24", strict=False).network_address), 24)
    except Exception:
        return ("192.168.1.0", 24)


def _subnet_hosts(limit: int = MAX_HOSTS) -> list[str]:
    """Yerel alt ağdaki taranabilir adresleri üretir."""
    net_addr, prefix = local_subnet()
    try:
        net = ipaddress.ip_network(f"{net_addr}/{prefix}", strict=False)
    except Exception:
        return []
    if net.num_addresses > 256:
        # Çok geniş ağlarda yalnızca ilk /24'ü tara.
        net = ipaddress.ip_network(f"{local_ipv4()}/24", strict=False)
    hosts = [str(h) for h in net.hosts()]
    return hosts[:limit]


def _is_usable(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if not addr.version == 4:
        return False
    if addr.is_loopback or addr.is_multicast or addr.is_unspecified:
        return False
    for net in _SKIP_NETS:
        if addr in net:
            return False
    return True


# ----------------------------------------------------------------------------
# Pasif keşif: ARP / komşu tablosu
# ----------------------------------------------------------------------------

def read_arp_table() -> dict[str, str]:
    """İşletim sisteminin ARP tablosunu {ip: mac} olarak döndürür.

    Windows'ta ``arp -a``, diğer sistemlerde ``ip neigh`` denenir. Hiçbir
    paket gönderilmez; yalnızca mevcut tablo okunur.
    """
    commands: list[list[str]] = []
    if os.name == "nt":
        commands.append(["arp", "-a"])
    else:
        commands.append(["ip", "neigh"])
        commands.append(["arp", "-an"])

    result: dict[str, str] = {}
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
                creationflags=_no_window_flag(),
            )
        except Exception:
            continue
        text = completed.stdout or ""
        if not text:
            continue
        for match in _ARP_ROW_RE.finditer(text):
            ip = match.group("ip")
            mac = match.group("mac").replace(":", "-").lower()
            if mac in {"ff-ff-ff-ff-ff-ff", "00-00-00-00-00-00"}:
                continue
            if not _is_usable(ip):
                continue
            result[ip] = mac
        if result:
            break
    return result


def passive_devices() -> list[dict[str, Any]]:
    """Hiç paket göndermeden bilinen cihazları listeler."""
    arp = read_arp_table()
    devices: list[dict[str, Any]] = []
    for ip, mac in sorted(arp.items(), key=lambda item: ipaddress.ip_address(item[0])):
        devices.append(
            {
                "ip": ip,
                "mac": mac,
                "hostname": "",
                "vendor": "",
                "open_ports": [],
                "source": "arp",
            }
        )
    return devices


# ----------------------------------------------------------------------------
# Aktif keşif: ping süpürme
# ----------------------------------------------------------------------------

def ping_host(ip: str, timeout_ms: int = PING_TIMEOUT_MS) -> bool:
    """Tek ICMP echo ile host'un ayakta olup olmadığını döndürür."""
    if os.name == "nt":
        command = ["ping", "-n", "1", "-w", str(int(timeout_ms)), ip]
    else:
        command = ["ping", "-c", "1", "-W", str(max(1, int(timeout_ms / 1000))), ip]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=HOST_TIMEOUT_S,
            creationflags=_no_window_flag(),
        )
        return completed.returncode == 0
    except Exception:
        return False


def prime_arp(hosts: Iterable[str], ports: tuple[int, ...] = (9, 80), wait_s: float = PRIME_WAIT_S) -> int:
    """ARP tablosunu hızlı doldurur (ICMP beklemeden).

    Her adrese çok küçük bir UDP datagramı gönderilir. Bu, işletim sisteminin
    o adres için ARP çözümlemesi yapmasını tetikler. Cevap beklenmez, bu yüzden
    ping süpürmesinden kat kat hızlıdır ve ICMP'yi engelleyen ağlarda da çalışır.

    Gönderilen bayt sayısını döndürür. Hiçbir servise bağlanılmaz, veri
    gönderilmez; datagram boştur.
    """
    sent = 0
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except Exception:
        return 0
    try:
        sock.setblocking(False)
        for ip in hosts:
            if not _is_usable(ip):
                continue
            for port in ports:
                try:
                    sock.sendto(b"", (ip, int(port)))
                    sent += 1
                except Exception:
                    continue
    finally:
        try:
            sock.close()
        except Exception:
            pass
    if sent and wait_s > 0:
        time.sleep(wait_s)
    return sent


def sweep(
    hosts: Iterable[str],
    workers: int = SWEEP_WORKERS,
    deadline: float | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Verilen adresleri sınırlı eşzamanlılıkla yoklar."""
    host_list = list(hosts)
    alive: list[str] = []
    total = len(host_list)
    if not total:
        return alive
    done = 0
    lock = threading.Lock()

    def worker(ip: str) -> None:
        nonlocal done
        if deadline is not None and time.monotonic() > deadline:
            return
        if ping_host(ip):
            with lock:
                alive.append(ip)
        with lock:
            done += 1
            current = done
        if on_progress is not None and (current % 16 == 0 or current == total):
            try:
                on_progress(current, total)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=max(1, min(workers, total))) as pool:
        list(pool.map(worker, host_list))
    return sorted(alive, key=lambda value: ipaddress.ip_address(value))


# ----------------------------------------------------------------------------
# İsim ve üretici çözümleme
# ----------------------------------------------------------------------------

def resolve_hostname(ip: str, timeout: float = 1.2) -> str:
    """Ters DNS ile host adını bulur.

    Ters DNS, PTR kaydı olmayan cihazlarda saniyelerce bloke edebilir. Bu yüzden
    arama ayrı bir iş parçacığında yapılır ve katı bir duvar saati sınırıyla
    kesilir; tarama asla tek bir cihaz yüzünden beklemez.
    """
    box: dict[str, str] = {"name": ""}

    def worker() -> None:
        try:
            box["name"] = str(socket.gethostbyaddr(ip)[0] or "").strip()
        except Exception:
            box["name"] = ""

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(max(0.2, float(timeout)))
    return box["name"]


def _mac_prefix(mac: str) -> str:
    return str(mac or "").replace(":", "-").lower()[:8]


def load_vendor_cache() -> dict[str, str]:
    try:
        raw = _vendor_cache_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_vendor_cache(cache: dict[str, str]) -> None:
    try:
        path = _vendor_cache_path()
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    except Exception:
        pass


def lookup_vendor_online(mac: str, cache: dict[str, str] | None = None) -> str:
    """MAC üreticisini çevrimiçi sorgular ve önbelleğe alır.

    Bu fonksiyon yalnızca kullanıcı açıkça istediğinde çağrılır. Hiçbir veri
    yüklenmez; yalnızca MAC ön eki sorgulanır.
    """
    prefix = _mac_prefix(mac)
    if not prefix:
        return ""
    store = cache if cache is not None else load_vendor_cache()
    if prefix in store:
        return store[prefix]
    vendor = ""
    try:
        import urllib.request

        request = urllib.request.Request(
            f"https://api.macvendors.com/{prefix}",
            headers={"User-Agent": "NetOps-NetworkScan/1.0"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            if 200 <= int(response.status) < 300:
                vendor = response.read(120).decode("utf-8", errors="replace").strip()
    except Exception:
        vendor = ""
    store[prefix] = vendor
    _save_vendor_cache(store)
    return vendor


# ----------------------------------------------------------------------------
# Port kontrolü
# ----------------------------------------------------------------------------

def check_ports(
    ip: str,
    ports: Iterable[int] = COMMON_PORTS,
    workers: int = 8,
) -> list[int]:
    """Yaygın portlarda TCP bağlantı denemesi yapar (isteğe bağlı).

    Portlar paralel denenir; sıralı deneme tek bir cihaz için saniyeler
    sürerdi. Hiçbir veri gönderilmez, yalnızca bağlantı açılıp kapatılır.
    """
    port_list = [int(p) for p in ports]
    if not port_list:
        return []

    def probe(port: int) -> int | None:
        try:
            with socket.create_connection((ip, port), timeout=PORT_TIMEOUT_S):
                return port
        except Exception:
            return None

    found: list[int] = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(port_list)))) as pool:
            for result in pool.map(probe, port_list):
                if result is not None:
                    found.append(result)
    except Exception:
        return sorted(found)
    return sorted(found)


# ----------------------------------------------------------------------------
# Envanter
# ----------------------------------------------------------------------------

def _now() -> float:
    return time.time()


def load_inventory() -> dict[str, Any]:
    """Yerel envanteri okur. Bozuksa boş yapı döner (asla hata fırlatmaz)."""
    try:
        raw = _inventory_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("devices"), dict):
            return data
    except Exception:
        pass
    return {"version": 1, "subnet": "", "devices": {}, "updated_at": 0.0}


def _save_inventory(data: dict[str, Any]) -> None:
    try:
        path = _inventory_path()
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    except Exception:
        pass


def _device_key(device: dict[str, Any]) -> str:
    mac = str(device.get("mac") or "").strip().lower()
    if mac:
        return f"mac:{mac}"
    return f"ip:{str(device.get('ip') or '').strip()}"


def merge_into_inventory(
    devices: list[dict[str, Any]],
    subnet: str = "",
) -> dict[str, Any]:
    """Tarama sonucunu envanterle birleştirir; yeni cihazları işaretler.

    Mevcut kayıtlar korunur (first_seen, seen_count, kullanıcı notları).
    """
    with _lock:
        inventory = load_inventory()
        if subnet:
            inventory["subnet"] = subnet
        known: dict[str, Any] = inventory.get("devices") or {}
        new_devices: list[dict[str, Any]] = []
        now = _now()

        for device in devices:
            key = _device_key(device)
            record = known.get(key)
            if record is None:
                record = {
                    "ip": device.get("ip", ""),
                    "mac": device.get("mac", ""),
                    "hostname": device.get("hostname", ""),
                    "vendor": device.get("vendor", ""),
                    "open_ports": list(device.get("open_ports") or []),
                    "first_seen": now,
                    "last_seen": now,
                    "seen_count": 1,
                    "is_new": True,
                    "note": "",
                }
                known[key] = record
                new_devices.append(dict(record))
            else:
                record["ip"] = device.get("ip") or record.get("ip", "")
                if device.get("mac"):
                    record["mac"] = device["mac"]
                if device.get("hostname"):
                    record["hostname"] = device["hostname"]
                if device.get("vendor"):
                    record["vendor"] = device["vendor"]
                if device.get("open_ports"):
                    record["open_ports"] = list(device["open_ports"])
                record["last_seen"] = now
                record["seen_count"] = int(record.get("seen_count") or 0) + 1
                record["is_new"] = False

        inventory["devices"] = known
        inventory["updated_at"] = now
        _save_inventory(inventory)
        return {"inventory": inventory, "new_devices": new_devices, "total": len(known)}


def inventory_summary() -> dict[str, Any]:
    """Kayıtlı envanterin özetini döndürür."""
    inventory = load_inventory()
    devices = list((inventory.get("devices") or {}).values())
    devices.sort(key=lambda item: str(item.get("ip") or ""))
    new_count = sum(1 for item in devices if item.get("is_new"))
    return {
        "total": len(devices),
        "new": new_count,
        "subnet": inventory.get("subnet", ""),
        "updated_at": inventory.get("updated_at", 0.0),
        "devices": devices,
    }


# ----------------------------------------------------------------------------
# Tarama orkestrasyonu
# ----------------------------------------------------------------------------

def _enrich(
    devices: list[dict[str, Any]],
    with_hostnames: bool,
    with_ports: bool,
    with_vendors: bool,
    deadline: float,
) -> None:
    """Cihaz kayıtlarını isim/port/üretici bilgisiyle zenginleştirir (yerinde).

    Üç aşama da paralel çalışır. Sıralı çalıştırıldığında ters DNS ve port
    denemeleri taramayı dakikalara çıkarıyordu; bu yüzden her aşama kendi
    havuzunda ve katı zaman aşımlarıyla yürütülür.
    """
    if not devices:
        return

    def collect(
        targets: list[dict[str, Any]],
        fn: Callable[[dict[str, Any]], Any],
        workers: int,
    ) -> list[Any]:
        if not targets or time.monotonic() > deadline:
            return []
        try:
            with ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as pool:
                return list(pool.map(fn, targets))
        except Exception:
            return []

    # 1) Ters DNS — en yavaş adım, bu yüzden geniş havuz.
    if with_hostnames:
        targets = [d for d in devices if not d.get("hostname")]
        values = collect(targets, lambda d: resolve_hostname(str(d.get("ip") or "")), 16)
        for device, value in zip(targets, values):
            if value:
                device["hostname"] = str(value)

    # 2) Port taraması — isteğe bağlı, kendi içinde de paralel.
    if with_ports:
        targets = [d for d in devices if not d.get("open_ports")]
        values = collect(targets, lambda d: check_ports(str(d.get("ip") or "")), 6)
        for device, value in zip(targets, values):
            if value:
                device["open_ports"] = list(value)

    # 3) MAC üreticisi — çevrimiçi sorgu, önbellekli, dar havuz.
    if with_vendors:
        cache = load_vendor_cache()
        targets = [d for d in devices if not d.get("vendor") and d.get("mac")]
        values = collect(targets, lambda d: lookup_vendor_online(str(d["mac"]), cache), 6)
        for device, value in zip(targets, values):
            if value:
                device["vendor"] = str(value)


def scan(
    mode: str = "active",
    include_hostnames: bool = True,
    include_ports: bool = False,
    include_vendors: bool = False,
    on_progress: Callable[[str], None] | None = None,
    budget_seconds: float = SCAN_BUDGET_S,
) -> dict[str, Any]:
    """Ağı tarar ve sonucu döndürür.

    mode:
        "passive" -> yalnızca ARP tablosu (hiç paket gönderilmez)
        "active"  -> hızlı ARP yoklaması (varsayılan, ~2 sn)
        "deep"    -> ARP yoklaması + gerçek ping süpürmesi (yavaş, daha kapsamlı)

    Hiçbir durumda istisna fırlatmaz; hata bilgisi ``error`` alanında döner.
    """
    started = time.monotonic()
    deadline = started + max(3.0, float(budget_seconds))
    net_addr, prefix = local_subnet()
    subnet = f"{net_addr}/{prefix}"
    result: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "subnet": subnet,
        "local_ip": local_ipv4(),
        "alive": [],
        "devices": [],
        "new_devices": [],
        "total_known": 0,
        "scanned_hosts": 0,
        "duration": 0.0,
        "error": "",
        "truncated": False,
        "warning": "",
    }

    def notify(message: str) -> None:
        if on_progress is not None:
            try:
                on_progress(message)
            except Exception:
                pass

    try:
        if mode == "passive":
            notify("ARP tablosu okunuyor (pasif, paket gönderilmiyor)...")
            devices = passive_devices()
            result["alive"] = [item["ip"] for item in devices]
        else:
            hosts = _subnet_hosts()
            result["scanned_hosts"] = len(hosts)
            alive: list[str] = []
            if mode == "deep":
                # Derin tarama: ARP yoklaması + gerçek ping süpürmesi.
                notify(f"{len(hosts)} adres ARP ile yoklanıyor...")
                prime_arp(hosts, wait_s=PRIME_WAIT_S)
                notify(f"{len(hosts)} adres ping ile doğrulanıyor...")
                alive = sweep(hosts, deadline=deadline)
            else:
                # Hızlı tarama: yalnızca ARP yoklaması (ICMP beklemesi yok).
                notify(f"{len(hosts)} adres için hızlı ARP yoklaması...")
                prime_arp(hosts)
            result["alive"] = alive
            if time.monotonic() > deadline:
                result["truncated"] = True
            # ARP tablosu, ping'e cevap vermeyen ama tabloda görünen cihazları da yakalar.
            arp = read_arp_table()
            merged: dict[str, dict[str, Any]] = {}
            for ip in alive:
                merged[ip] = {
                    "ip": ip,
                    "mac": arp.get(ip, ""),
                    "hostname": "",
                    "vendor": "",
                    "open_ports": [],
                    "source": "ping",
                }
            for ip, mac in arp.items():
                if ip in merged:
                    if not merged[ip].get("mac"):
                        merged[ip]["mac"] = mac
                    merged[ip]["source"] = "ping+arp"
                else:
                    merged[ip] = {
                        "ip": ip,
                        "mac": mac,
                        "hostname": "",
                        "vendor": "",
                        "open_ports": [],
                        "source": "arp",
                    }
            devices = [merged[key] for key in sorted(merged, key=lambda v: ipaddress.ip_address(v))]

        notify(f"{len(devices)} cihaz bulundu. Bilgiler tamamlanıyor...")
        _enrich(devices, include_hostnames, include_ports, include_vendors, deadline)

        merged_info = merge_into_inventory(devices, subnet=subnet)
        result["devices"] = devices
        result["new_devices"] = merged_info["new_devices"]
        result["total_known"] = merged_info["total"]
    except Exception as exc:  # asla yukarı sızdırma
        result["ok"] = False
        result["error"] = str(exc)
    result["duration"] = round(time.monotonic() - started, 2)
    return result


# ----------------------------------------------------------------------------
# Rapor biçimlendirme
# ----------------------------------------------------------------------------

def _device_line(index: int, device: dict[str, Any]) -> str:
    ip = str(device.get("ip") or "?")
    mac = str(device.get("mac") or "—")
    hostname = str(device.get("hostname") or "").strip()
    vendor = str(device.get("vendor") or "").strip()
    ports = device.get("open_ports") or []
    extras: list[str] = []
    try:
        if ip == local_ipv4():
            extras.append("bu bilgisayar")
    except Exception:
        pass
    if hostname:
        extras.append(hostname)
    if vendor:
        extras.append(vendor)
    if ports:
        extras.append("port: " + ",".join(str(p) for p in ports))
    suffix = ("  (" + " · ".join(extras) + ")") if extras else ""
    return f"{index:>2}. {ip:<15} {mac}{suffix}"


def format_report(result: dict[str, Any], show_new_only: bool = False) -> str:
    """Tarama sonucunu sohbete uygun Türkçe metne çevirir."""
    if not result:
        return "Ağ taraması sonuç döndürmedi."
    if not result.get("ok"):
        return f"Ağ taraması tamamlanamadı: {result.get('error') or 'bilinmeyen hata'}"

    devices = result.get("devices") or []
    new_devices = result.get("new_devices") or []
    mode_map = {
        "passive": "pasif (yalnızca ARP, paket gönderilmedi)",
        "active": "hızlı (ARP yoklaması)",
        "deep": "derin (ping + port)",
    }
    mode = mode_map.get(str(result.get("mode") or "active"), "aktif")
    lines: list[str] = []

    if show_new_only:
        if not new_devices:
            lines.append("Ağda yeni cihaz yok. Kayıtlı düzen aynı.")
            lines.append(f"Toplam kayıtlı cihaz: {result.get('total_known', 0)}")
            return "\n".join(lines)
        lines.append(f"🆕 {len(new_devices)} yeni cihaz bulundu:")
        for index, device in enumerate(new_devices, start=1):
            lines.append(_device_line(index, device))
        lines.append("")
        lines.append("Bunlar daha önce görülmemişti. Tanımıyorsanız ağınızı kontrol edin.")
        return "\n".join(lines)

    lines.append(f"📡 Ağ taraması — {mode}")
    lines.append(f"Yerel adres: {result.get('local_ip')}   Alt ağ: {result.get('subnet')}")
    if result.get("mode") != "passive":
        lines.append(f"Yoklanan adres: {result.get('scanned_hosts')}")
    lines.append(f"Bulunan cihaz: {len(devices)}   Süre: {result.get('duration')} sn")
    lines.append("")

    if not devices:
        lines.append("Cihaz bulunamadı. Güvenlik duvarı ICMP'yi engelliyor olabilir;")
        lines.append("'ağ envanteri' komutu ARP tablosundan pasif liste verir.")
        return "\n".join(lines)

    subnet_prefix = str(result.get("subnet") or "").split("/")[0].rsplit(".", 1)[0]
    for index, device in enumerate(devices, start=1):
        lines.append(_device_line(index, device))

    if new_devices:
        lines.append("")
        lines.append(f"🆕 Bu taramada {len(new_devices)} yeni cihaz kaydedildi:")
        for index, device in enumerate(new_devices, start=1):
            lines.append(_device_line(index, device))

    if result.get("truncated"):
        lines.append("")
        lines.append("⚠️ Süre bütçesi doldu, tarama erken bitti. Tekrar deneyin.")
    lines.append("")
    lines.append(f"Envanterdeki toplam kayıt: {result.get('total_known', 0)}")
    if subnet_prefix:
        lines.append(f"Not: Yalnızca {subnet_prefix}.x alt ağı tarandı.")
    return "\n".join(lines)


def inventory_text() -> str:
    """Kayıtlı envanteri metin olarak döndürür."""
    summary = inventory_summary()
    devices = summary.get("devices") or []
    if not devices:
        return "Henüz kayıtlı cihaz yok. 'ağı tara' ile başlayın."
    lines = [f"🗂️ Cihaz envanteri — {summary.get('total', 0)} kayıt"]
    if summary.get("subnet"):
        lines.append(f"Alt ağ: {summary.get('subnet')}")
    updated = float(summary.get("updated_at") or 0.0)
    if updated:
        lines.append("Son güncelleme: " + time.strftime("%d.%m.%Y %H:%M", time.localtime(updated)))
    lines.append("")
    for index, device in enumerate(devices, start=1):
        line = _device_line(index, device)
        if device.get("is_new"):
            line += "  🆕"
        lines.append(line)
    if summary.get("new"):
        lines.append("")
        lines.append(f"🆕 {summary['new']} cihaz henüz tanınmadı ('yeni cihazlar' komutu).")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Sohbet / sesli komut köprüsü
# ----------------------------------------------------------------------------

# Komut eşleştirme KATI ifade listesiyle yapılır. Gevşek anahtar kelime
# kullanılmaz; böylece "bu cihazın ağ bağlantısı nasıl?" gibi normal sohbet
# cümleleri bu modüle takılmaz ve mevcut davranış bozulmaz.
_PANEL_PHRASES = (
    "ağ panelini aç", "ağ paneli aç", "ag panelini ac",
    "ağ tarayıcıyı aç", "ağ tarayıcısını aç", "ağ tarayıcı aç",
    "ağ panelini göster", "ağ tarayıcıyı göster", "ağ tarayıcısını göster",
    "lan panelini aç", "network panel aç", "ağ panelini başlat",
)
_NEW_PHRASES = (
    "yeni cihaz", "yeni cihazlar", "yeni cihaz var", "yeni cihaz çıktı",
    "bilinmeyen cihaz", "bilinmeyen cihazlar", "ağda yeni cihaz",
)
_INVENTORY_PHRASES = (
    "cihaz envanteri", "ağ envanteri", "ag envanteri",
    "envanter listesi", "kayıtlı cihazlar", "kayitli cihazlar",
    "cihaz listesi", "ağdaki cihazlar", "ağdaki cihazları",
    "ağ cihazları", "ag cihazlari", "lan cihazları",
)
_SCAN_PHRASES = (
    "ağ tara", "ağı tara", "ag tara", "agi tara",
    "ağ tarama", "ağ taraması", "ağ taramasını", "ağ taraması yap",
    "lan tara", "lan taraması", "network scan",
    "yerel ağı tara", "yerel agi tara",
    "ağda kim var", "agda kim var", "ağı yokla", "agi yokla",
)
_DETAIL_WORDS = ("detaylı", "detayli", "derin", "port")
_NET_HINTS = ("ağ", "ag", "lan", "network")


def _mentions_network(text: str) -> bool:
    return any(word in text for word in _NET_HINTS)


_PHRASE_CACHE: dict[str, "re.Pattern[str]"] = {}


def _find_phrase(text: str, phrases: tuple[str, ...]) -> str:
    """İfadeyi KELİME SINIRI ile arar.

    Sınır şarttır: "ağ tara" ifadesi "ağ tarafında" cümlesine takılmaz,
    böylece normal sohbet yanlışlıkla taramaya yönlenmez.
    """
    for phrase in phrases:
        pattern = _PHRASE_CACHE.get(phrase)
        if pattern is None:
            pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
            _PHRASE_CACHE[phrase] = pattern
        if pattern.search(text):
            return phrase
    return ""


def _open_window_safe() -> str:
    """Ana uygulamanın Tk kökünü bularak pencereyi açar (yalnızca ekleme)."""
    try:
        import tkinter as tk

        root = getattr(tk, "_default_root", None)
        if root is None:
            return "Ağ paneli için önce NetOps penceresinin açık olması gerekiyor."
        palette: dict[str, Any] = {}
        try:
            main = sys.modules.get("__main__")
            palette = dict(getattr(main, "aktif_palet", {}) or {})
        except Exception:
            palette = {}
        network_scan_ac(parent=root, palette=palette)
        return "Ağ tarayıcı paneli açıldı."
    except Exception as exc:
        return f"Ağ paneli açılamadı: {exc}"


def _new_device_report() -> str:
    summary = inventory_summary()
    new_devices = [item for item in summary.get("devices") or [] if item.get("is_new")]
    return format_report(
        {
            "ok": True,
            "mode": "active",
            "devices": new_devices,
            "new_devices": new_devices,
            "total_known": summary.get("total", 0),
            "local_ip": local_ipv4(),
            "subnet": summary.get("subnet", ""),
            "duration": 0.0,
        },
        show_new_only=True,
    )


def _passive_list_text() -> str:
    devices = passive_devices()
    if not devices:
        return "ARP tablosu boş. 'ağı tara' ile aktif tarama yapabilirsiniz."
    lines = [f"📡 Ağdaki bilinen cihazlar ({len(devices)}) — pasif ARP listesi", ""]
    for index, device in enumerate(devices, start=1):
        lines.append(_device_line(index, device))
    lines.append("")
    lines.append("Aktif tarama: 'ağı tara'  •  Detaylı: 'detaylı ağ taraması'")
    return "\n".join(lines)


def handle_command(text: str) -> str | None:
    """Sohbet/sesli komutu işler.

    Yalnızca açıkça ağ taraması isteyen kalıplarda metin döndürür; aksi halde
    ``None`` döndürerek ana uygulamanın normal akışına hiç karışmaz.
    """
    try:
        raw = str(text or "").strip()
        if not raw or len(raw) > 300:
            return None
        lowered = raw.casefold().replace("i̇", "i")
        if not _mentions_network(lowered):
            return None

        if _find_phrase(lowered, _PANEL_PHRASES):
            return _open_window_safe()

        if _find_phrase(lowered, _NEW_PHRASES):
            return _new_device_report()

        if _find_phrase(lowered, _INVENTORY_PHRASES):
            return inventory_text()

        if _find_phrase(lowered, _SCAN_PHRASES):
            detailed = any(word in lowered for word in _DETAIL_WORDS)
            result = scan(
                mode="deep" if detailed else "active",
                include_hostnames=True,
                include_ports=detailed,
                include_vendors=detailed,
                budget_seconds=SCAN_BUDGET_S,
            )
            return format_report(result)

        return None
    except Exception as exc:
        try:
            print(f"[NETWORK_SCAN_CMD_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return None


# ----------------------------------------------------------------------------
# Arayüz (mevcut NetOps pencere kalıbına uygun)
# ----------------------------------------------------------------------------

def network_scan_ac(parent=None, T=None, palette=None, say_callback=None):
    """Ağ tarayıcı panelini açar. Mevcut pencere varsa onu öne getirir."""
    global _window_ref
    import customtkinter as ctk

    colors = palette or {}
    background = colors.get("bg", "#0F0F14")
    card = colors.get("card", "#181820")
    text_main = colors.get("text_main", "#FFFFFF")
    text_dim = colors.get("text_dim", "#9CA3AF")
    accent = colors.get("neon", "#22C55E")

    if _window_ref is not None:
        try:
            if _window_ref.winfo_exists():
                _window_ref.deiconify()
                _window_ref.lift()
                _window_ref.focus_force()
                return _window_ref
        except Exception:
            _window_ref = None

    window = ctk.CTkToplevel(parent) if parent is not None else ctk.CTkToplevel()
    _window_ref = window
    window.title("NetOps Ağ Tarayıcı")
    window.geometry("820x660")
    window.configure(fg_color=background)
    try:
        window.transient(parent)
    except Exception:
        pass

    ctk.CTkLabel(
        window,
        text="Ağ Tarayıcı ve Cihaz Envanteri",
        font=("Segoe UI Semibold", 22),
        text_color=text_main,
    ).pack(pady=(16, 2))
    ctk.CTkLabel(
        window,
        text="Yalnızca yerel ağ • Pasif ARP + sınırlı ping • Sömürü/parola denemesi yok",
        font=("Segoe UI", 11),
        text_color=text_dim,
    ).pack(pady=(0, 10))

    info = ctk.CTkLabel(
        window,
        text=f"Yerel adres: {local_ipv4()}   •   Alt ağ: {local_subnet()[0]}/{local_subnet()[1]}",
        font=("Segoe UI", 11),
        text_color=text_dim,
    )
    info.pack(pady=(0, 6))

    status = ctk.CTkLabel(window, text="Hazır.", text_color=text_dim, font=("Segoe UI", 11), wraplength=760)
    status.pack(fill="x", padx=20, pady=(0, 6))

    output = ctk.CTkTextbox(window, fg_color=card, text_color=text_main, font=("Consolas", 11), wrap="none")
    output.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    actions = ctk.CTkFrame(window, fg_color="transparent")
    actions.pack(fill="x", padx=20, pady=(0, 16))

    busy = {"value": False}

    def set_output(value: str) -> None:
        output.delete("1.0", "end")
        output.insert("1.0", str(value))

    def set_status(value: str) -> None:
        try:
            status.configure(text=str(value))
        except Exception:
            pass

    def _run_in_thread(target: Callable[[], None]) -> None:
        if busy["value"]:
            return
        busy["value"] = True
        for button in buttons:
            try:
                button.configure(state="disabled")
            except Exception:
                pass

        def wrapper() -> None:
            try:
                target()
            finally:
                busy["value"] = False
                try:
                    window.after(
                        0,
                        lambda: [
                            button.configure(state="normal")
                            for button in buttons
                            if button.winfo_exists()
                        ],
                    )
                except Exception:
                    pass

        threading.Thread(target=wrapper, daemon=True).start()

    def post(callback: Callable[[], None]) -> None:
        try:
            window.after(0, callback)
        except Exception:
            pass

    def do_passive() -> None:
        def job() -> None:
            post(lambda: set_status("ARP tablosu okunuyor..."))
            devices = passive_devices()
            lines = [f"Pasif ARP listesi — {len(devices)} cihaz", ""]
            if not devices:
                lines.append("Tabloda cihaz yok. Aktif tarama deneyin.")
            for index, device in enumerate(devices, start=1):
                lines.append(_device_line(index, device))
            text = "\n".join(lines)
            post(lambda: (set_output(text), set_status(f"{len(devices)} cihaz (pasif).")))

        _run_in_thread(job)

    def do_active(detailed: bool) -> None:
        def job() -> None:
            post(lambda: set_status("Aktif tarama sürüyor..."))

            def progress(message: str) -> None:
                post(lambda: set_status(message))

            result = scan(
                mode="deep" if detailed else "active",
                include_hostnames=True,
                include_ports=detailed,
                include_vendors=detailed,
                on_progress=progress,
                budget_seconds=SCAN_BUDGET_S,
            )
            report = format_report(result)
            post(lambda: (set_output(report), set_status(f"Bitti — {result.get('duration')} sn.")))

        _run_in_thread(job)

    def do_inventory() -> None:
        text = inventory_text()
        set_output(text)
        set_status("Kayıtlı envanter gösteriliyor.")

    def do_new() -> None:
        summary = inventory_summary()
        new_devices = [item for item in summary.get("devices") or [] if item.get("is_new")]
        report = format_report(
            {
                "ok": True,
                "mode": "active",
                "devices": new_devices,
                "new_devices": new_devices,
                "total_known": summary.get("total", 0),
                "local_ip": local_ipv4(),
                "subnet": summary.get("subnet", ""),
                "duration": 0.0,
            },
            show_new_only=True,
        )
        set_output(report)
        set_status(f"{len(new_devices)} yeni cihaz.")

    def close() -> None:
        global _window_ref
        try:
            if _window_ref is window:
                _window_ref = None
        except Exception:
            _window_ref = None
        try:
            window.destroy()
        except Exception:
            pass

    buttons: list[Any] = []
    definitions = (
        ("Pasif listele (ARP)", lambda: do_passive(), accent),
        ("Ağı tara", lambda: do_active(False), accent),
        ("Detaylı tara", lambda: do_active(True), None),
        ("Envanter", lambda: do_inventory(), None),
        ("Yeni cihazlar", lambda: do_new(), None),
        ("Kapat", lambda: close(), None),
    )
    for label, command, color in definitions:
        kwargs: dict[str, Any] = {
            "text": label,
            "command": command,
            "font": ("Segoe UI Semibold", 12),
            "corner_radius": 10,
            "height": 34,
        }
        if color:
            kwargs["fg_color"] = color
            kwargs["text_color"] = "#0B0B10"
        else:
            kwargs["fg_color"] = card
            kwargs["text_color"] = text_main
        button = ctk.CTkButton(actions, **kwargs)
        button.pack(side="left", padx=(0, 8))
        buttons.append(button)

    set_output(
        "Hoş geldiniz.\n\n"
        "• 'Pasif listele'  → hiç paket göndermeden ARP tablosunu okur.\n"
        "• 'Ağı tara'       → yerel alt ağı yoklar (ping + ARP).\n"
        "• 'Detaylı tara'   → ek olarak yaygın portlar ve MAC üreticisi.\n"
        "• 'Envanter'       → daha önce görülen cihazlar.\n"
        "• 'Yeni cihazlar'  → ilk kez görülen cihazlar.\n\n"
        "Not: Tarama yalnızca yerel alt ağınızda çalışır ve sınırlıdır."
    )
    if callable(say_callback):
        try:
            say_callback("Ağ tarayıcı hazır.")
        except Exception:
            pass
    return window
