import json
import os

try:
    from config import get_data_path
except Exception:
    def get_data_path(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

try:
    from neto_version import APP_TITLE_EN, APP_TITLE_TR
except Exception:
    APP_TITLE_TR = "NetOps v1.42.0"
    APP_TITLE_EN = APP_TITLE_TR


HAFIZA_DOSYA = get_data_path("hafiza.json")


LANG = {
    "tr": {
        "app_title": APP_TITLE_TR,
        "language_selection": "Dil Seçimi",
        "language_title": "NetOps'e Hoş Geldin",
        "language_desc": "Lütfen uygulama dilini seç.",
        "turkish": "Türkçe",
        "english": "English",
        "loading": "Açılıyor...",
        "system_status": "Sistem Durumu",
        "notes": "📌 Notlar",
        "system": "⚙️ Sistem",
        "netolab": "⚙️ NetOps Lab",
        "advanced_settings": "🔧 Gelişmiş Ayarlar",
        "neto_ai": "🌐 Web Sohbeti",
        "android_device": "📱 Android Cihaz",
        "device_hub": "🔗 Cihaz Bağla / QR",
        "language": "🌐 Dil",
        "extension_status_off": "Eklenti Durumu: KAPALI",
        "extension_status_on": "Eklenti Durumu: AÇIK",
        "extension_store": "🛒 Eklenti Mağazası",
        "main_question": "Sana nasıl yardımcı olabilirim?",
        "welcome_question": "Sana nasıl yardımcı olabilirim?",
        "main_hello": "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim? 👋",
        "hello_text": "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim? 👋",
        "send": "Gönder",
        "entry_placeholder": "Mesajını yaz...",
        "thinking": "Düşünüyor...",
        "ready": "Hazır.",
        "tts_unavailable": "⚠️ Yerel TTS kullanılamıyor. Model indirilemedi ya da yüklenemedi.",
        "polite_warning": "⚠️ Bu şekilde konuşamam. Daha kibar yazarsan yardımcı olurum.",
        "goodbye": "Görüşürüz! Kendine iyi bak 😊",
        "thanks_reply": "Rica ederim! 🙏",
        "how_are_you": "İyiyim, sana nasıl yardımcı olabilirim?",
        "who_are_you": "Ben NetOps, senin kişisel asistanınım.",
        "ai_greeting_1": "Merhaba! Buradayım, ne lazım?",
        "ai_greeting_2": "Selam! Sana nasıl yardımcı olayım?",
        "ai_greeting_3": "Hey! Buradayım, neye bakıyoruz?",
        "ai_how_are_you_short": "İyiyim, bayağı iyiyim. Sen nasılsın?",
        "ai_how_are_you_short_2": "İyiyim, enerjim yerinde. Sende durumlar nasıl?",
        "ai_thanks_reply_short": "Rica ederim, ne demek.",
        "ai_thanks_reply_short_2": "Her zaman, sorun değil.",
        "ai_goodbye_short": "Görüşürüz, kendine iyi bak.",
        "ai_goodbye_short_2": "Sonra yine gel, beklerim.",
        "ai_default_1": "Bunu net bilmiyorum ama birlikte çözebiliriz.",
        "ai_default_2": "Kısa cevap: şu an kesin değil, ama bakmamı istersen yardımcı olurum.",
        "ai_default_3": "Buna doğrudan cevap veremem; biraz daha detay verirsen netleşir.",
        "ai_default_4": "Bunun için internette hızlıca bakmam gerekir; istersen hemen kontrol edeyim.",
        "ai_default_5": "Net bir sonuç yok, ama farklı şekilde sorarsan daha iyi sonuç alabiliriz.",
        "ai_default_6": "Şu an elimde tek bir net cevap yok; istersen web üzerinden arayayım.",
        "ai_default_7": "Bunu tahmin etmek istemem; güvenilir bir kaynakla kontrol etmek daha iyi olur.",
        "ai_default_8": "Bana bir ipucu daha verirsen daha sağlam cevap çıkarırım.",
        "chat_no_answer": "Cevap alınamadı.",
        "not_understood": "Bunu tam anlayamadım.",
        "ask_learning": "Bunu öğrenmemi ister misin?",
        "help_text": "Yardım: Komut yazabilir, ayarları açabilir veya NetOps Agent kullanabilirsin.",
        "main_opening_run": "Açılıyor...",
        "main_opening_code": "Kod editörü açılıyor...",
        "main_opening_netolab": "NetOps Lab açılıyor...",
        "main_opening_advanced": "Gelişmiş ayarlar açılıyor...",
        "live_confirm_title": "NetOps Live Mode",
        "live_confirm_msg": "Live Mode'a geçmek istediğine emin misin?\n\nAsistan kapanacak ve NetOps Live açılacak.",
        "live_back_title": "NetOps Live",
        "live_back_msg": "Asistana geri dönmek istiyor musun?\n\nLive Mode kapanacak ve NetOps açılacak.",
        "live_start": "▶ Başlat",
        "live_stop": "⏸ Durdur",
        "live_closed": "Kapalı",
        "live_starting": "Başlatılıyor...",
        "live_mic_waiting": "Mikrofon: Bekleniyor",
        "live_voice": "Ses: Yerel Piper Türkçe Erkek",
        "live_error": "Hata",
        "ai_start_title": "NetOps Agent Başlatılıyor",
        "ai_start_message": "İnternet tabanlı cevap motoru hazır.\n\nDevam etmek istiyor musun?",
        "ai_preparing_title": "NetOps Web Sohbeti Hazırlanıyor",
        "ai_preparing": "🌐 İnternet cevap motoru hazırlanıyor...",
        "ollama_checking": "İnternet bağlantısı kontrol ediliyor...",
        "ollama_api_checking": "Arama sonuçları kontrol ediliyor...",
        "ollama_starting": "Web sohbeti başlatılıyor...",
        "model_list_checking": "Arama listesi kontrol ediliyor...",
        "model_downloading": "Web cevap sistemi hazırlanıyor...",
        "model_ready": "Cevap sistemi hazır. Sohbet açılıyor...",
        "ollama_needed_title": "Web Sohbeti Hazır",
        "ollama_needed_msg": "Web tabanlı cevap motoru hazır.\n\nMesajını yazabilirsin.",
        "ollama_start_failed_title": "Web Sohbeti Başlatılamadı",
        "ollama_start_failed_msg": "Web cevap motoru şu an cevap vermiyor.",
        "ai_error_title": "NetOps Agent Hatası",
        "model_list_failed": "Model listesi alınamadı.",
        "model_download_started_title": "Web Sohbeti Hazırlanıyor",
        "model_download_started_msg": "Web cevap sistemi hazırlanıyor.",
        "model_download_failed": "Web sohbeti başlatılamadı:\n{error}",
        "ai_prepare_error": "Web sohbeti hazırlanırken hata oluştu:\n{error}",
        "ai_time_now": "Şu an saat {time}",
        "ai_date_today": "Bugün {day} {month} {year}",
        "ai_empty_input": "Bir şey yazmadın.",
        "ai_developer": "Beni NetOps geliştirdi.",
        "ai_no_news": "Elimde okunacak haber yok. Önce 'bugün haber var mı?' diye sor.",
        "ai_current_info_failed": "Güncel bilgiye ulaşamadım. İnternet araması sonuç vermedi.",
        "ai_empty_response": "Cevap boş geldi.",
        "ai_model_not_ready": "Web cevap modu kapalı. İnternet tabanlı yanıt sistemi açılmalı.",
        "ai_ollama_service_not_running": "Web cevap motoru şu an hazır değil. Biraz bekleyip tekrar dene.",
        "ai_timeout": "Cevap çok geç geldi. Biraz bekleyip tekrar dene.",
        "tray_title": "NetOps",
        "tray_show": "NetOps'u Göster",
        "tray_exit": "Çıkış",
        "tray_minimized_info": "NetOps tepsiye alındı. Arka planda çalışmaya devam ediyor. Geri açmak için tepsi simgesine çift tıkla.",
    },
    "en": {
        "app_title": APP_TITLE_EN,
        "language_selection": "Language Selection",
        "language_title": "Welcome to NetOps",
        "language_desc": "Please select the app language.",
        "turkish": "Türkçe",
        "english": "English",
        "loading": "Opening...",
        "system_status": "System Status",
        "notes": "📌 Notes",
        "system": "⚙️ System",
        "netolab": "⚙️ NetOps Lab",
        "advanced_settings": "🔧 Advanced Settings",
        "neto_ai": "🌐 Web Chat",
        "android_device": "📱 Android Device",
        "device_hub": "🔗 Connect Device / QR",
        "language": "🌐 Language",
        "extension_status_off": "Extension Status: OFF",
        "extension_status_on": "Extension Status: ON",
        "extension_store": "🛒 Extension Store",
        "main_question": "How can I help you?",
        "welcome_question": "How can I help you?",
        "main_hello": "Hello! I am NetOps. How can I help you? 👋",
        "hello_text": "Hello! I am NetOps. How can I help you? 👋",
        "send": "Send",
        "entry_placeholder": "Type your message...",
        "thinking": "Thinking...",
        "ready": "Ready.",
        "tts_unavailable": "⚠️ Local TTS unavailable. The model could not be downloaded or loaded.",
        "polite_warning": "⚠️ I cannot continue like this. Please write more politely.",
        "goodbye": "Goodbye! Take care 😊",
        "thanks_reply": "You're welcome! 🙏",
        "how_are_you": "I'm good. How can I help you?",
        "who_are_you": "I am NetOps, your personal assistant.",
        "ai_greeting_1": "Hello! I'm here, what do you need?",
        "ai_greeting_2": "Hi! How can I help you?",
        "ai_greeting_3": "Hey! I'm here, what are we looking at?",
        "ai_how_are_you_short": "I'm good, really good. How about you?",
        "ai_how_are_you_short_2": "I'm good and full of energy. How are you?",
        "ai_thanks_reply_short": "You're welcome, no problem.",
        "ai_thanks_reply_short_2": "Anytime, no worries.",
        "ai_goodbye_short": "See you later, take care.",
        "ai_goodbye_short_2": "Come back anytime, I'll be here.",
        "ai_default_1": "I do not know for sure, but we can figure it out together.",
        "ai_default_2": "Short answer: not certain yet, but I can help check.",
        "ai_default_3": "I can't answer that directly; give me a bit more detail and I'll narrow it down.",
        "ai_default_4": "I should check the web for that; if you want, I can do it now.",
        "ai_default_5": "No solid result yet, but a different wording may work better.",
        "ai_default_6": "I don't have one exact answer, so a web lookup would help more.",
        "ai_default_7": "I would rather verify that with a reliable source than guess.",
        "ai_default_8": "Give me one more hint and I'll get you a sharper answer.",
        "chat_no_answer": "No response received.",
        "not_understood": "I did not fully understand that.",
        "ask_learning": "Do you want me to learn this?",
        "help_text": "Help: You can type a command, open settings, or use NetOps Agent.",
        "main_opening_run": "Opening...",
        "main_opening_code": "Opening code editor...",
        "main_opening_netolab": "Opening NetOps Lab...",
        "main_opening_advanced": "Opening advanced settings...",
        "live_confirm_title": "NetOps Live Mode",
        "live_confirm_msg": "Are you sure you want to switch to Live Mode?\n\nAssistant will close and NetOps Live will open.",
        "live_back_title": "NetOps Live",
        "live_back_msg": "Do you want to return to Assistant?\n\nLive Mode will close and NetOps will open.",
        "live_start": "▶ Start",
        "live_stop": "⏸ Stop",
        "live_closed": "Closed",
        "live_starting": "Starting...",
        "live_mic_waiting": "Microphone: Waiting",
        "live_voice": "Voice: Local Piper Turkish Male",
        "live_error": "Error",
        "ai_start_title": "Starting NetOps Agent",
        "ai_start_message": "The web-based reply engine is ready.\n\nDo you want to continue?",
        "ai_preparing_title": "Preparing NetOps Web Chat",
        "ai_preparing": "🌐 Preparing the web reply engine...",
        "ollama_checking": "Checking internet connection...",
        "ollama_api_checking": "Checking search results...",
        "ollama_starting": "Starting web chat...",
        "model_list_checking": "Checking search list...",
        "model_downloading": "Preparing the web reply system...",
        "model_ready": "Reply system is ready. Opening chat...",
        "ollama_needed_title": "Web Chat Ready",
        "ollama_needed_msg": "The web-based reply engine is ready.\n\nYou can chat now.",
        "ollama_start_failed_title": "Could Not Start Web Chat",
        "ollama_start_failed_msg": "The web reply engine is not responding right now.",
        "ai_error_title": "NetOps Agent Error",
        "model_list_failed": "Could not get the model list.",
        "model_download_started_title": "Preparing Web Chat",
        "model_download_started_msg": "The web reply system is being prepared.",
        "model_download_failed": "Could not start the web chat:\n{error}",
        "ai_prepare_error": "An error occurred while preparing the web chat:\n{error}",
        "ai_time_now": "The time is {time}",
        "ai_date_today": "Today is {day} {month} {year}",
        "ai_empty_input": "You did not type anything.",
        "ai_developer": "I was developed by NetOps.",
        "ai_no_news": "I do not have any news to read. First ask 'is there news today?'",
        "ai_current_info_failed": "I could not get current information. The internet search did not return results.",
        "ai_empty_response": "The reply came back empty.",
        "ai_model_not_ready": "The web reply mode is off. The internet-based reply system needs to be enabled.",
        "ai_ollama_service_not_running": "The web reply engine is not ready right now. Try again after a moment.",
        "ai_timeout": "The reply took too long. Try again after a moment.",
        "tray_title": "NetOps",
        "tray_show": "Show NetOps",
        "tray_exit": "Quit",
        "tray_minimized_info": "NetOps moved to tray. It keeps running in the background. Double-click the tray icon to reopen.",
    },
}


def _load_memory():
    try:
        if os.path.exists(HAFIZA_DOSYA):
            with open(HAFIZA_DOSYA, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_memory(data):
    try:
        with open(HAFIZA_DOSYA, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_lang() -> str:
    data = _load_memory()
    lang = str(data.get("dil", "en")).lower()
    return lang if lang in LANG else "en"


def set_lang(lang) -> str:
    lang = str(lang or "").lower()
    if lang not in LANG:
        lang = "en"
    data = _load_memory()
    data["dil"] = lang
    _save_memory(data)
    return lang


def T(key: str, **kwargs) -> str:
    lang = get_lang()
    text = LANG.get(lang, LANG["en"]).get(key)
    if text is None:
        text = LANG["en"].get(key, LANG["tr"].get(key, key))
    if not isinstance(text, str):
        text = str(key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return str(text)
