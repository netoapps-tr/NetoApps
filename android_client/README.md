# NetOps Android istemcisi

Bu klasör masaüstü NetOps uygulamasından ayrı, 2 GB RAM'li tabletler için hafif Android istemcisidir. Python, Lua runtime, Whisper veya Ollama içermez.

## Uyarlanabilir ekran

- Telefon, küçük tablet ve geniş tablet için farklı yatay boşluklar kullanır.
- Dikey/yatay yön değişiminde aynı sohbet düzeni yeniden ölçülür.
- Sohbet geçmişi esnek alanı kaplar; mesaj çubuğu ekranın altına sabitlenir.
- `adjustResize` ile klavye açıldığında input bar görünür kalır.
- Ağır geçiş animasyonu ve büyük görsel kullanılmaz.

## Derleme

Bu makinede şu an Android SDK ve Gradle kurulu değil. Android Studio veya command-line SDK kurulduktan sonra:

```text
cd android_client
gradle :app:assembleDebug
```

PowerShell ile ön kontrol ve derleme için `./build_android.ps1` kullanılabilir. SDK veya Gradle eksikse betik açık hata verir; sessizce başarısız APK üretmez.

APK yolu:

```text
android_client/app/build/outputs/apk/debug/app-debug.apk
```

İlk iskelet bilinçli olarak platform Android View'ları kullanır; böylece ek UI kütüphanesi indirmeden düşük kaynaklı tablette çalışır. Sonraki adım, mevcut NetOps yerel hafıza ve timer adapter'larını bu istemciye bağlamak ve gerçek cihazda portrait/landscape testidir.

## Doğrulanan cihaz testi

İlk APK, Android 15 kullanan `RMX3890` cihazında açıldı. `1080x2400` ekran ve yaklaşık `360dp` portre genişliğinde mesaj yazma, gönderme ve yerel yanıt kartı akışı doğrulandı.
