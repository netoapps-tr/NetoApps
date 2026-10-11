# NETOPS Kolay Surum
# Bu dosya kodlama ogrenmen ve asistani anlaman icin sade tutuldu.

import random
import tkinter as tk
from tkinter import ttk


UYGULAMA_ADI = "NETOPS Kolay"

# Yeni cevap eklemek icin bu sozluge yeni satir ekle.
# Sol taraf: kullanicinin yazabilecegi kelime
# Sag taraf: asistanin verebilecegi cevaplar
KOMUTLAR = {
    "selam": [
        "Selam, buradayim.",
        "Hos geldin, sistemi dinliyorum.",
    ],
    "merhaba": [
        "Merhaba, ne yapalim?",
        "Buradayim, komutunu bekliyorum.",
    ],
    "yanimda kiz var": [
        "Tamam, sakin ve karizmatik mod acildi.",
        "Anladim, ortami bozmayacak sekilde cevap veriyorum.",
    ],
    "kendini kontrol et": [
        "Mini kontrol tamam. Arayuz calisiyor, komut motoru aktif.",
    ],
    "doktor": [
        "Mini Doktor hazir. Ana projede TTS, mikrofon ve modul kontrolu yapabiliriz.",
    ],
    "arduino": [
        "Arduino isi simdilik beklemede. Once uygulama beynini saglamlastiralim.",
    ],
}

GENEL_CEVAPLAR = [
    "Bunu tam anlamadim ama cevap vermeyi birakmiyorum.",
    "Bu komutu henuz ogrenmedim. Istersen bunu KOMUTLAR listesine ekleyebiliriz.",
    "Buradayim. Bana bunu biraz daha kisa yazarsan yakalarim.",
]


def metni_temizle(metin: str) -> str:
    """Karsilastirma kolay olsun diye yaziyi kucultur ve bosluklari toplar."""
    return " ".join(str(metin or "").lower().strip().split())


def cevap_bul(kullanici_metni: str) -> str:
    """Kullanici yazisina en basit sekilde cevap bulur."""
    temiz = metni_temizle(kullanici_metni)
    if not temiz:
        return "Once bir sey yaz, sonra ben cevap vereyim."

    for anahtar, cevaplar in KOMUTLAR.items():
        if anahtar in temiz:
            return random.choice(cevaplar)

    return random.choice(GENEL_CEVAPLAR)


class KolayNetops:
    def __init__(self) -> None:
        self.pencere = tk.Tk()
        self.pencere.title(UYGULAMA_ADI)
        self.pencere.geometry("640x420")
        self.pencere.minsize(520, 340)

        self.pencere.configure(bg="#101114")
        self._arayuzu_kur()

    def _arayuzu_kur(self) -> None:
        baslik = tk.Label(
            self.pencere,
            text="NETOPS Kolay Mod",
            bg="#101114",
            fg="#f4f4f5",
            font=("Segoe UI", 22, "bold"),
        )
        baslik.pack(pady=(28, 8))

        self.cevap = tk.Label(
            self.pencere,
            text="Mesaj yaz, ben cevap vereyim.",
            bg="#101114",
            fg="#60a5fa",
            wraplength=540,
            font=("Segoe UI", 13),
        )
        self.cevap.pack(pady=16)

        kutu = tk.Frame(self.pencere, bg="#101114")
        kutu.pack(side="bottom", fill="x", padx=24, pady=24)

        self.giris = ttk.Entry(kutu)
        self.giris.pack(side="left", fill="x", expand=True, ipady=8)
        self.giris.bind("<Return>", lambda _event: self.gonder())

        buton = ttk.Button(kutu, text="Gonder", command=self.gonder)
        buton.pack(side="left", padx=(10, 0), ipadx=12, ipady=6)

    def gonder(self) -> None:
        metin = self.giris.get()
        self.giris.delete(0, "end")
        self.cevap.configure(text=cevap_bul(metin))

    def calistir(self) -> None:
        self.pencere.mainloop()


if __name__ == "__main__":
    uygulama = KolayNetops()
    uygulama.calistir()
