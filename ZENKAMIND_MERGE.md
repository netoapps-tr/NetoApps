# NetOps / Zenkamind Birlesme Paketi

Bu paket, NetOps v1.42.0 kaynak kodunun Zenkamind altinda birlestirilmesi icin
hazirlanmistir.

## Giris noktasi

- Ana masaustu uygulamasi: `asistan beta.py`
- Windows paket ayari: `NetOps.spec`
- EXE build scripti: `BUILD_EXE.ps1`
- Android/Termux calisma alani: `android_client/`
- Eklenti sistemi: `plugins/` ve `*.nops`

## Birlesme notlari

- Kullanici hafizasi, loglar, cache ve yerel ayarlar pakete dahil edilmedi.
- `dist/`, `build/` ve eski yedek klasorleri pakete dahil edilmedi; bunlar eski
  veya makineye ozel uretim ciktilaridir.
- Zenkamind entegrasyonu yapilirken `neto_version.py`, `netops_system_manifest.json`
  ve `config.py` birlikte gozden gecirilmelidir.
- Yeni EXE, kaynaklar birlestirildikten sonra `BUILD_EXE.ps1` ile uretilmelidir.

## Kontrol komutlari

```powershell
python -m py_compile "asistan beta.py" neto_motion_engine_v2.py neto_now_playing.py
python -m unittest discover -s tests -p "test_*.py" -q
powershell -ExecutionPolicy Bypass -File .\BUILD_EXE.ps1
```

## Son guncelleme

- Now Playing sol paneli taze medya bilgisiyle periyodik yenilenir.
- Sohbet ekranina donuste gizlenen metin cubugu ve ana sohbet yuzeyi geri yuklenir.
- Acilis animasyonu pencere boyutunu oynatmadan akici opaklik gecisi kullanir.
