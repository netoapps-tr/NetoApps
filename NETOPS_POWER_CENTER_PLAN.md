# NetOps Power Center

Bu belge, acik kaynak projelerden esinlenen yeteneklerin NetOps icindeki guvenli
adaptasyonunu izler. Harici uygulamalar NetOps icine gomulmez; kuruluysa
algilanir ve kullanicinin istegiyle acilir.

## Hazir olanlar

- Komut Paleti: mevcut NetOps komut paletine Power Center ve entegrasyon komutlari eklendi.
- Cihazlar Merkezi: mevcut KDE Connect benzeri cihaz hub'i korunuyor.
- Otomasyon Sahneleri: mevcut planla-onayla-uygula-dogrula-geri al dongusu korunuyor.
- Ekran Yakalama: PIL veya pyautogui ile yerel PNG kaydi; yukleme yok.
- Aktivite Ozeti: varsayilan kapali, sadece `NETOPS_ACTIVITY_ENABLED=1` ile yerel kayit.
- Metin Sablonlari: yerel ve atomik JSON kaydi.
- Senkronizasyon Manifesti: dosya kopyalamadan envanter cikarir.
- Eklenti Guvenligi: mevcut statik tarama ve izin kapisi kullanilir.
- Node-RED: mevcut loopback akisi opsiyonel olarak kullanilir.

## Dis arac adaptorlari

NetOps su uygulamalari PATH uzerinden algilayabilir: Flow Launcher, PowerToys,
KDE Connect, LocalSend, Syncthing, Espanso, OBS Studio, KeePassXC ve RustDesk.
Bulunmayan uygulama hata olarak degil, `kurulu degil` olarak gosterilir.

## Muhafazakar hata tahmini

Bu oranlar istatistiksel garanti degildir; test kapsami, dis bagimlilik ve OS
izinleri dikkate alinarak gelistirme planlamasi icin kullanilir.

| Yetenek | Tahmini hata riski | Ana neden | Koruma |
| --- | ---: | --- | --- |
| Komut paleti | %3 | UI callback veya tema farki | Mevcut palette testleri |
| Cihazlar merkezi | %12 | Ag, firewall, cihaz izni | Timeout, pairing ve offline fallback |
| Otomasyon sahneleri | %10 | Windows izinleri ve hedef uygulama | Plan, onay, dogrulama, rollback |
| Ekran yakalama | %8 | Uzak masaustu, DPI, ekran izni | PIL -> pyautogui fallback |
| Aktivite ozeti | %4 | Kapatilmis opt-in kayit | Varsayilan kapali ve atomik yazim |
| Metin sablonlari | %3 | Bozuk yerel JSON | Boyut siniri ve atomik yazim |
| Sync manifesti | %7 | Kilitli dosya veya uzun yol | Symlink atlama, dosya limiti |
| Dis uygulama acma | %15 | PATH, kurulum yeri, surum | Sadece allowlist; ham komut yok |
| Node-RED | %12 | Servis kapali veya port engeli | Opsiyonel bridge, timeout, no-op fallback |

## Bilerek sonraya birakilanlar

- Tam Syncthing/LocalSend protokolunu yeniden yazmak.
- KeePassXC sifre kasasini NetOps icinde yeniden uygulamak.
- RustDesk ile uzaktan kontrol baslatmak. Bu ozellik ayri kimlik dogrulama,
  kullanici onayi ve denetim kaydi olmadan acilmayacak.
- Global klavye hook'u. Once izin ekrani, disable anahtari ve test matrisi
  tamamlanmadan arka planda dinleme yapilmayacak.
- Otomatik OCR motoru indirmek. Kurulu degilse ekran yakalama OCR'siz devam eder.

## Kontrol

Kaynakta EXE uretilmedi. Son dogrulama:

```text
33 passed
```

Yeni kaynak degisikliklerinden sonra EXE build'i ayri ve kullanici onayi ile
yapilmalidir.
