# NetOps Shell for Termux

Bu istemci, root veya ayrı bir AI modeli istemeden Termux üzerinden aynı yerel
Wi-Fi ağındaki Windows NetOps'a bağlanır. Windows tarafı yetkili merkezdir;
Remote ekranındaki sohbet, doğrulanmış WebSocket üzerinden Termux ajanına
güvenli yerel sorular gönderebilir. Uzak kabuk, rastgele dosya erişimi veya
keyfi komut çalıştırma yoktur.

## Kurulum

Termux'ta proje klasörü GitHub'dan alındıktan sonra:

```sh
pkg update
pkg install python git
cd NetoApps/mobile/termux
sh install.sh
```

Bu kurulum ağdan Python paketi indirmez. Komut `netops` adıyla Termux'a eklenir.

## Eşleştirme

Windows NetOps içinde **Remote** ekranını açıp sunucuyu
başlat. Aynı ekrandaki PC yerel adresini ve tek kullanımlık kodu kullan:

```sh
netops pair --host 192.168.1.20:8765 --code 123456 --name "Telefonum"
```

Eşleştirme tamamlandıktan sonra telefonu Remote ekranında sürekli çevrimiçi
tutmak için Termux'ta ayrı bir oturumda şu komutu açık bırak:

```sh
netops agent --name "Telefonum"
```

Bu işlem yalnızca heartbeat gönderir; çıkmak için `Ctrl+C` kullanılır.

Eşleşme bilgisi yalnızca Termux cihazında şu dosyada tutulur:
`~/.config/netops-shell/config.json`. Token terminale yazdırılmaz.

## NetOps ile Termux sohbeti

NetOps Remote ekranındaki **Termux sohbeti** kutusundan şu tür sorular
gönderilebilir:

```text
Termux durumu nedir?
RAM ne kadar?
Telefon çalışıyor mu?
```

Yanıtlar telefondaki yerel ve salt-okunur bilgilerden üretilir. Keyfi shell
metni, silme komutu veya root işlemi sohbet üzerinden çalıştırılmaz.

## Komutlar

```sh
netops ask "sistem durumunu göster"
netops status
netops ram
netops cpu
netops disk
netops ağ
netops uptime
netops battery
netops commands
netops core-restart
netops recovery
netops ask onayla
netops ask iptal
netops reboot
netops poweroff
netops devices
netops key up
netops key c
netops control
netops now-playing
netops now-playing --watch --interval 5
netops play-pause
netops next
netops previous
netops volume 35
netops --json status
netops forget
```

`netops recovery` önce Windows NetOps'a bir onay isteği gönderir. Güncel Termux
kurulumu bu onayı otomatik olarak tam ekran bir menüye taşır; yukarı/aşağı ve
Enter ile **ONAYLA**, Esc veya ikinci seçenek ile **İPTAL** seçilir. Eski
kurulumlarda `netops ask onayla` ve `netops ask iptal` komutları çalışmaya
devam eder.

`netops control` güvenli kontrol modudur: yön tuşları PC'deki aktif pencereye
gönderilir; `c/e/f/v/s/n/x/a` sırasıyla Chrome, Edge, Firefox, VS Code,
Spotify, Not Defteri, Dosya Gezgini ve Windows Ayarları'nı açar. `q` ile
kontrol modu kapanır. Rastgele tuşlar, klavye kombinasyonları ve kabuk komutları
uzaktan çalıştırılmaz.

Bağlantı sadece yerel ağ için tasarlanmıştır. Port 8765'i internete açma veya
port yönlendirme yapma. Kodun süresi dolarsa Device Hub'dan yeni kod üretip
yeniden `pair` çalıştır.
