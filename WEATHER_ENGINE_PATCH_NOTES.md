# NetOps Weather Engine Patch

Bu paket `00.zip` içindeki güncel NetOps kaynakları üzerine hazırlanmıştır.

## Uygulanan ana değişiklikler

- Rüzgar birimi `km/s` -> `km/sa` düzeltildi.
- `kar`, `radar`, `fırtına`, `şimşek`, `dolu`, `sis`, `buz`, `don`, `AQI`, `hava kalitesi`, `polen`, `METAR`, `sel/taşkın` sorguları Weather Engine router'ına eklendi.
- `Ankara'da kar yağacak mı?` gibi geçici şehir sorguları düzeltildi.
- Ana asistan ve `neto_sohbet_v3.py` içindeki ayrı `wttr.in` yolları kaldırılıp merkezi `neto_weather` motoruna yönlendirildi.
- Open-Meteo ana tahmine wet-bulb, snowfall height, surface/soil temperature, CAPE/CIN ve 925/850/700/500 hPa katmanları eklendi.
- Air Quality artık mümkün olduğunda saat 00:00 yerine `current` verisini kullanır.
- Gerçek Open-Meteo ensemble sağlayıcısı eklendi:
  - ECMWF IFS ENS
  - GFS GEFS
  - ICON EPS
  - Google WeatherNext 2 (başarısız olursa diğerleri devam eder)
- Ayrı deterministik ECMWF/GFS/ICON karşılaştırması eklendi.
- Kar analizi artık geçmiş günün ilk 24 saatini değil, sorgu anından sonraki pencereyi analiz eder; `yarın kar` sorgusu yarının saatlerini seçer.
- Kar motoru wet-bulb, 925/850 hPa, freezing level, snowfall height, yüzey ve toprak sıcaklığı ile ensemble mutabakatını birleştirir.
- Open-Meteo Flood sağlayıcısı eklendi.
- HTTP katmanına 429/5xx retry, `Retry-After`, exponential backoff ve stale-cache fallback eklendi.
- Cache'e eski kayıt temizleme desteği eklendi.
- `BUILD_EXE.ps1` içine `--collect-submodules neto_weather_engine` eklendi.

## Kurulum

Bu paketin içeriğini NetOps proje köküne kopyala ve mevcut dosyaların üzerine yaz.

Ardından test:

```powershell
python -m compileall -q neto_weather.py neto_weather_engine neto_sohbet_v3.py "asistan beta.py"
```

EXE üretmek için mevcut `BUILD_EXE.ps1` dosyasını çalıştırabilirsin.

## Not

Bu ortam dış internete doğrudan bağlanamadığı için gerçek API çağrıları runtime'da burada çalıştırılamadı. Endpoint/model adları güncel resmi Open-Meteo dokümantasyonuna göre yazıldı ve sentetik JSON testleriyle parser/router akışı doğrulandı.

Rainbow Weather ve Pirate Weather ücretsiz katmanları API key gerektirdiği için bu patch'te aktif edilmedi. Anahtarlar daha sonra NetOps'un DPAPI kasasına bağlanmalı.
