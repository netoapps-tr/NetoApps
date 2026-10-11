package com.netops.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONObject;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Lightweight remote client. Tablets do not run Python, Lua or a model;
 * they only connect to a paired NetOps PC when one is available.
 */
public final class MainActivity extends Activity {
    private static final int BACKGROUND = Color.rgb(8, 9, 13);
    private static final int SURFACE = Color.rgb(18, 21, 28);
    private static final int SURFACE_ALT = Color.rgb(25, 29, 38);
    private static final int STROKE = Color.rgb(43, 51, 66);
    private static final int ACCENT = Color.rgb(79, 124, 255);
    private static final int GREEN = Color.rgb(32, 199, 102);
    private static final int TEXT = Color.rgb(244, 247, 251);
    private static final int MUTED = Color.rgb(142, 154, 175);
    private static final Pattern PRIVATE_IPV4 = Pattern.compile("^(10|192\\.168|172\\.(1[6-9]|2[0-9]|3[0-1])|169\\.254)\\.[0-9.]+$");

    private DeviceStore store;
    private final ArrayList<DeviceStore.Device> devices = new ArrayList<>();
    private DeviceStore.Device selectedDevice;
    private NetOpsLinkClient link;

    private LinearLayout root;
    private FrameLayout content;
    private LinearLayout header;
    private TextView pageTitle;
    private TextView connectionStatus;
    private Button headerAction;
    private LinearLayout messageColumn;
    private ScrollView chatScroll;
    private EditText messageInput;
    private TextView pendingStatus;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BACKGROUND);
        getWindow().setNavigationBarColor(BACKGROUND);
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        store = new DeviceStore(this);
        devices.addAll(store.load());
        buildShell();
        showDeviceCenter();
        if (!devices.isEmpty()) {
            connectTo(devices.get(0));
        }
    }

    @Override
    protected void onDestroy() {
        if (link != null) {
            link.disconnect();
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (selectedDevice != null && messageColumn != null) {
            showDeviceCenter();
            return;
        }
        super.onBackPressed();
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        applyResponsiveLayout();
    }

    private void buildShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BACKGROUND);
        header = buildHeader();
        root.addView(header, new LinearLayout.LayoutParams(-1, dp(70)));
        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
    }

    private LinearLayout buildHeader() {
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(16), dp(8), dp(16), dp(8));

        TextView logo = text("N", 18, TEXT, Typeface.BOLD);
        logo.setGravity(Gravity.CENTER);
        logo.setBackground(round(ACCENT, 18, 0));
        bar.addView(logo, new LinearLayout.LayoutParams(dp(36), dp(36)));

        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.setPadding(dp(12), 0, dp(8), 0);
        pageTitle = text("NetOps", 18, TEXT, Typeface.BOLD);
        connectionStatus = text("Bağlı cihaz yok", 11, MUTED, Typeface.NORMAL);
        titles.addView(pageTitle);
        titles.addView(connectionStatus);
        bar.addView(titles, new LinearLayout.LayoutParams(0, -2, 1f));

        headerAction = actionButton("Cihaz ekle", ACCENT);
        headerAction.setOnClickListener(view -> {
            if (messageColumn != null) {
                showDeviceCenter();
            } else {
                showAddDialog("", "", "");
            }
        });
        bar.addView(headerAction, new LinearLayout.LayoutParams(-2, dp(42)));
        return bar;
    }

    private void showDeviceCenter() {
        messageColumn = null;
        pageTitle.setText("Cihazlar");
        headerAction.setText("Cihaz ekle");
        headerAction.setOnClickListener(view -> showAddDialog("", "", ""));
        if (selectedDevice == null) {
            setConnectionStatus("Bağlı cihaz yok", false);
        }

        content.removeAllViews();
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(16), dp(12), dp(16), dp(18));

        TextView intro = text("Bu uygulama yalnızca eşleştirilmiş NetOps PC'ye bağlanır.", 14, MUTED, Typeface.NORMAL);
        intro.setPadding(dp(4), dp(4), dp(4), dp(14));
        page.addView(intro);

        if (devices.isEmpty()) {
            LinearLayout empty = new LinearLayout(this);
            empty.setOrientation(LinearLayout.VERTICAL);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(20), dp(42), dp(20), dp(42));
            empty.setBackground(round(SURFACE, 24, STROKE));
            TextView title = text("Bağlı cihaz yok", 22, TEXT, Typeface.BOLD);
            title.setGravity(Gravity.CENTER);
            TextView hint = text("Sağ üstten Cihaz ekle ile PC'nin yerel IP adresini ve eşleştirme kodunu gir.", 14, MUTED, Typeface.NORMAL);
            hint.setGravity(Gravity.CENTER);
            hint.setPadding(dp(20), dp(10), dp(20), 0);
            empty.addView(title);
            empty.addView(hint);
            page.addView(empty, new LinearLayout.LayoutParams(-1, -2));
        } else {
            for (DeviceStore.Device device : devices) {
                page.addView(deviceCard(device), new LinearLayout.LayoutParams(-1, -2));
            }
        }
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.addView(page, new ScrollView.LayoutParams(-1, -2));
        content.addView(scroll, new FrameLayout.LayoutParams(-1, -1));
        applyResponsiveLayout();
    }

    private LinearLayout deviceCard(DeviceStore.Device device) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(14));
        card.setBackground(round(SURFACE, 22, STROKE));

        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView name = text(device.displayName(), 17, TEXT, Typeface.BOLD);
        titleRow.addView(name, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView status = text(isSelected(device) && link != null && link.isConnected() ? "BAĞLI" : "ÇEVRİMDIŞI", 11,
                isSelected(device) && link != null && link.isConnected() ? GREEN : MUTED, Typeface.BOLD);
        titleRow.addView(status);
        card.addView(titleRow);

        TextView address = text(device.address, 13, MUTED, Typeface.NORMAL);
        address.setPadding(0, dp(5), 0, dp(10));
        card.addView(address);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        Button connect = actionButton(isSelected(device) && link != null && link.isConnected() ? "Sohbete dön" : "Bağlan", ACCENT);
        connect.setOnClickListener(view -> {
            if (isSelected(device) && link != null && link.isConnected()) {
                showChat();
            } else {
                connectTo(device);
            }
        });
        Button remove = actionButton("Sil", SURFACE_ALT);
        remove.setTextColor(MUTED);
        remove.setOnClickListener(view -> {
            store.remove(device);
            devices.clear();
            devices.addAll(store.load());
            if (isSelected(device)) {
                selectedDevice = null;
                if (link != null) {
                    link.disconnect();
                }
            }
            showDeviceCenter();
        });
        actions.addView(connect, new LinearLayout.LayoutParams(-2, dp(40)));
        LinearLayout.LayoutParams removeParams = new LinearLayout.LayoutParams(-2, dp(40));
        removeParams.setMargins(dp(8), 0, 0, 0);
        actions.addView(remove, removeParams);
        card.addView(actions);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, 0, 0, dp(10));
        card.setLayoutParams(params);
        return card;
    }

    private void showAddDialog(String addressPrefill, String namePrefill, String pairingPrefill) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(22), dp(8), dp(22), 0);

        EditText name = field("PC adı", namePrefill);
        EditText address = field("PC yerel IP adresi  (ör. 192.168.1.20:8765)", addressPrefill);
        EditText pairing = field("Eşleştirme kodu", pairingPrefill);
        address.setInputType(InputType.TYPE_CLASS_TEXT);
        pairing.setInputType(InputType.TYPE_CLASS_NUMBER);
        form.addView(name);
        form.addView(address, marginParams(0, 10, 0, 0));
        form.addView(pairing, marginParams(0, 10, 0, 0));

        Button qr = actionButton("QR kod ile tara", SURFACE_ALT);
        qr.setTextColor(TEXT);
        qr.setOnClickListener(view -> {
            IntentIntegrator integrator = new IntentIntegrator(this);
            integrator.setPrompt("NetOps PC'deki QR kodu okut");
            integrator.setBeepEnabled(false);
            integrator.setOrientationLocked(false);
            integrator.initiateScan();
        });
        form.addView(qr, marginParams(0, 12, 0, 0));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Cihaz ekle")
                .setView(form)
                .setNegativeButton("İptal", null)
                .setPositiveButton("Bağlan", null)
                .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String cleanAddress = normalizeAddress(address.getText().toString());
            String cleanCode = pairing.getText().toString().trim();
            if (!isLocalAddress(cleanAddress)) {
                address.setError("Aynı ağdaki PC IP adresini gir");
                return;
            }
            if (cleanCode.isEmpty()) {
                pairing.setError("İlk eşleştirmede kod gerekli");
                return;
            }
            DeviceStore.Device device = new DeviceStore.Device(
                    name.getText().toString().trim(), cleanAddress, "", "", cleanCode
            );
            store.upsert(device);
            devices.clear();
            devices.addAll(store.load());
            dialog.dismiss();
            connectTo(device);
        }));
        dialog.show();
    }

    private void connectTo(DeviceStore.Device device) {
        if (!isLocalAddress(device.address)) {
            Toast.makeText(this, "Yalnızca PC'nin yerel IP adresi kullanılabilir.", Toast.LENGTH_LONG).show();
            return;
        }
        selectedDevice = device;
        setConnectionStatus("PC'ye bağlanıyor...", false);
        if (link != null) {
            link.disconnect();
        }
        link = new NetOpsLinkClient(new NetOpsLinkClient.Listener() {
            @Override
            public void onState(String state) {
                runOnUiThread(() -> setConnectionStatus(state, "Bağlandı".equals(state)));
            }

            @Override
            public void onHello(String deviceId, String token) {
                runOnUiThread(() -> {
                    selectedDevice.deviceId = deviceId;
                    if (token != null && !token.isEmpty()) {
                        selectedDevice.token = token;
                    }
                    selectedDevice.pairingCode = "";
                    store.upsert(selectedDevice);
                    devices.clear();
                    devices.addAll(store.load());
                    showChat();
                });
            }

            @Override
            public void onMessage(JSONObject message) {
                runOnUiThread(() -> handleRemoteMessage(message));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    setConnectionStatus(message, false);
                    if (pendingStatus != null) {
                        pendingStatus.setText(message);
                    }
                });
            }

            @Override
            public void onDisconnected(String reason) {
                runOnUiThread(() -> setConnectionStatus(reason, false));
            }
        });
        link.connect(device);
    }

    private void showChat() {
        if (selectedDevice == null) {
            showDeviceCenter();
            return;
        }
        pageTitle.setText(selectedDevice.displayName());
        headerAction.setText("Cihazlar");
        headerAction.setOnClickListener(view -> showDeviceCenter());
        content.removeAllViews();

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(12), dp(8), dp(12), 0);

        chatScroll = new ScrollView(this);
        chatScroll.setFillViewport(true);
        chatScroll.setClipToPadding(false);
        chatScroll.setVerticalScrollBarEnabled(false);
        messageColumn = new LinearLayout(this);
        messageColumn.setOrientation(LinearLayout.VERTICAL);
        chatScroll.addView(messageColumn, new ScrollView.LayoutParams(-1, -2));
        page.addView(chatScroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout media = new LinearLayout(this);
        media.setGravity(Gravity.CENTER_VERTICAL);
        media.setPadding(0, dp(6), 0, dp(4));
        addMediaButton(media, "Şu an çalan", "current");
        addMediaButton(media, "Önceki", "previous");
        addMediaButton(media, "Oynat / duraklat", "play_pause");
        addMediaButton(media, "Sonraki", "next");
        page.addView(media, new LinearLayout.LayoutParams(-1, -2));

        pendingStatus = text("PC hazır", 11, MUTED, Typeface.NORMAL);
        pendingStatus.setPadding(dp(4), dp(2), dp(4), dp(2));
        page.addView(pendingStatus, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout input = buildInputBar();
        page.addView(input, new LinearLayout.LayoutParams(-1, -2));
        content.addView(page, new FrameLayout.LayoutParams(-1, -1));

        addMessage("PC'ye bağlandım. Artık komutlarını ve sorularını NetOps'a gönderebilirsin.", false);
        applyResponsiveLayout();
    }

    private LinearLayout buildInputBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(7), dp(5), dp(7), dp(5));
        bar.setBackground(round(SURFACE_ALT, 26, STROKE));

        ImageButton add = iconButton(com.netops.mobile.R.drawable.ic_plus, "Ek seçenekler");
        bar.addView(add, new LinearLayout.LayoutParams(dp(42), dp(42)));

        messageInput = new EditText(this);
        messageInput.setSingleLine(true);
        messageInput.setTextSize(15);
        messageInput.setTextColor(TEXT);
        messageInput.setHintTextColor(MUTED);
        messageInput.setHint("Mesajını yaz...");
        messageInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        messageInput.setImeOptions(EditorInfo.IME_ACTION_SEND);
        messageInput.setBackgroundColor(Color.TRANSPARENT);
        messageInput.setPadding(dp(8), 0, dp(8), 0);
        messageInput.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage();
                return true;
            }
            return false;
        });
        bar.addView(messageInput, new LinearLayout.LayoutParams(0, dp(48), 1f));

        ImageButton send = iconButton(com.netops.mobile.R.drawable.ic_send, "Gönder");
        send.setBackground(round(ACCENT, 22, 0));
        send.setPadding(dp(10), dp(10), dp(10), dp(10));
        send.setOnClickListener(view -> sendMessage());
        bar.addView(send, new LinearLayout.LayoutParams(dp(44), dp(44)));

        ImageButton mic = iconButton(com.netops.mobile.R.drawable.ic_mic, "Sesli giriş");
        mic.setOnClickListener(view -> Toast.makeText(this, "Sesli giriş sonraki mobil adımda açılacak.", Toast.LENGTH_SHORT).show());
        bar.addView(mic, new LinearLayout.LayoutParams(dp(42), dp(42)));
        return bar;
    }

    private void sendMessage() {
        String query = messageInput == null ? "" : messageInput.getText().toString().trim();
        if (query.isEmpty()) {
            return;
        }
        addMessage(query, true);
        messageInput.setText("");
        if (link == null || !link.isConnected()) {
            addMessage("Bağlı cihaz yok. Sağ üstten PC ekleyip eşleştirdikten sonra tekrar dene.", false);
            return;
        }
        pendingStatus.setText("NetOps yanıtı bekleniyor...");
        link.requestAssistant(query);
    }

    private void handleRemoteMessage(JSONObject message) {
        String type = message.optString("type", "");
        if ("assistant_response".equals(type)) {
            boolean ok = message.optBoolean("ok", false);
            String display = ok ? message.optString("display_text", "NetOps yanıt vermedi.") : friendlyError(message.optString("error", ""));
            addMessage(sanitizeDisplay(display), false);
            if (pendingStatus != null) {
                pendingStatus.setText(ok ? "PC hazır" : "Yanıt alınamadı");
            }
        } else if ("media_response".equals(type)) {
            boolean ok = message.optBoolean("ok", false);
            String display = ok ? message.optString("display_text", "Medya işlemi tamamlandı.") : friendlyError(message.optString("error", ""));
            if (pendingStatus != null) {
                pendingStatus.setText(sanitizeDisplay(display));
            }
        }
    }

    private void addMediaButton(LinearLayout row, String label, String action) {
        Button button = actionButton(label, SURFACE_ALT);
        button.setTextColor(TEXT);
        button.setTextSize(11);
        button.setOnClickListener(view -> {
            if (link == null || !link.isConnected()) {
                setConnectionStatus("PC bağlı değil", false);
                return;
            }
            pendingStatus.setText("Medya komutu gönderiliyor...");
            link.requestMedia(action);
        });
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(38), 1f);
        params.setMargins(dp(2), 0, dp(2), 0);
        row.addView(button, params);
    }

    private void addMessage(String message, boolean user) {
        if (messageColumn == null) {
            return;
        }
        TextView card = text(sanitizeDisplay(message), 15, TEXT, Typeface.NORMAL);
        card.setLineSpacing(0, 1.08f);
        card.setPadding(dp(16), dp(12), dp(16), dp(12));
        card.setBackground(round(user ? ACCENT : SURFACE, 20, user ? 0 : STROKE));
        card.setMaxWidth(dp(640));
        LinearLayout row = new LinearLayout(this);
        row.setGravity(user ? Gravity.END : Gravity.START);
        row.setPadding(0, dp(5), 0, dp(5));
        row.addView(card, new LinearLayout.LayoutParams(-2, -2));
        messageColumn.addView(row, new LinearLayout.LayoutParams(-1, -2));
        if (chatScroll != null) {
            chatScroll.post(() -> chatScroll.fullScroll(View.FOCUS_DOWN));
        }
    }

    private void setConnectionStatus(String status, boolean connected) {
        if (connectionStatus != null) {
            connectionStatus.setText(status);
            connectionStatus.setTextColor(connected ? GREEN : MUTED);
        }
    }

    private void applyResponsiveLayout() {
        if (header == null) {
            return;
        }
        int widthDp = Math.round(getResources().getDisplayMetrics().widthPixels / getResources().getDisplayMetrics().density);
        int horizontal = widthDp >= 840 ? 64 : widthDp >= 600 ? 32 : widthDp >= 420 ? 20 : 12;
        header.setPadding(horizontal, dp(8), horizontal, dp(8));
        if (messageColumn != null) {
            messageColumn.setPadding(horizontal, dp(widthDp >= 600 ? 24 : 16), horizontal, dp(16));
        }
    }

    private void scanResult(String contents) {
        try {
            String clean = contents == null ? "" : contents.trim();
            if (clean.startsWith("{")) {
                JSONObject payload = new JSONObject(clean);
                showAddDialog(
                        payload.optString("server", ""),
                        payload.optString("name", "NetOps PC"),
                        payload.optString("pairing_code", "")
                );
                return;
            }
            Uri uri = Uri.parse(clean);
            if ("netops".equalsIgnoreCase(uri.getScheme())) {
                showAddDialog(uri.getQueryParameter("server"), uri.getQueryParameter("name"), uri.getQueryParameter("code"));
                return;
            }
            Toast.makeText(this, "Bu QR kod NetOps eşleştirme kodu değil.", Toast.LENGTH_LONG).show();
        } catch (Exception error) {
            Toast.makeText(this, "QR kod okunamadı.", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        IntentResult result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (result != null) {
            if (result.getContents() != null) {
                scanResult(result.getContents());
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    private EditText field(String hint, String value) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setText(value == null ? "" : value);
        field.setTextColor(TEXT);
        field.setHintTextColor(MUTED);
        field.setSingleLine(true);
        field.setTextSize(14);
        field.setPadding(dp(12), 0, dp(12), 0);
        field.setBackground(round(SURFACE_ALT, 12, STROKE));
        field.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(48)));
        return field;
    }

    private Button actionButton(String label, int background) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(TEXT);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setMinHeight(0);
        button.setMinWidth(0);
        button.setPadding(dp(12), 0, dp(12), 0);
        button.setBackground(round(background, 14, background == SURFACE_ALT ? STROKE : 0));
        return button;
    }

    private ImageButton iconButton(int drawableId, String description) {
        ImageButton button = new ImageButton(this);
        button.setImageResource(drawableId);
        button.setContentDescription(description);
        button.setBackgroundColor(Color.TRANSPARENT);
        button.setPadding(dp(9), dp(9), dp(9), dp(9));
        button.setScaleType(ImageButton.ScaleType.CENTER_INSIDE);
        return button;
    }

    private LinearLayout.LayoutParams marginParams(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(48));
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom));
        return params;
    }

    private String normalizeAddress(String value) {
        String clean = value == null ? "" : value.trim();
        if (clean.isEmpty()) {
            return "";
        }
        if (!clean.contains("://")) {
            clean = "ws://" + clean;
        }
        try {
            URI uri = URI.create(clean);
            if (uri.getPort() < 0) {
                return uri.getScheme() + "://" + uri.getHost() + ":8765";
            }
            return clean;
        } catch (Exception ignored) {
            return clean;
        }
    }

    private boolean isLocalAddress(String value) {
        try {
            URI uri = URI.create(normalizeAddress(value));
            String host = uri.getHost();
            if (host == null || host.isEmpty()) {
                return false;
            }
            if ("localhost".equalsIgnoreCase(host) || "127.0.0.1".equals(host)) {
                return true;
            }
            return PRIVATE_IPV4.matcher(host).matches();
        } catch (Exception ignored) {
            return false;
        }
    }

    private boolean isSelected(DeviceStore.Device device) {
        return selectedDevice != null && (selectedDevice == device
                || (!selectedDevice.deviceId.isEmpty() && selectedDevice.deviceId.equals(device.deviceId)));
    }

    private String friendlyError(String error) {
        if (error == null || error.isEmpty()) {
            return "PC yanıt veremedi.";
        }
        if (error.contains("OFFLINE") || error.contains("UNAVAILABLE")) {
            return "NetOps PC şu anda hazır değil.";
        }
        return "İşlem tamamlanamadı.";
    }

    private String sanitizeDisplay(String value) {
        String clean = value == null ? "" : value;
        clean = clean.replaceAll("https?://\\S+", "");
        clean = clean.replaceAll("(?i)\\b(?:www\\.)?[^\\s]+\\.(?:com|org|net|io|tr)(?:/[^\\s]*)?", "");
        return clean.replaceAll("[ \\t]{2,}", " ").trim();
    }

    private TextView text(String value, float size, int color, int style) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(Typeface.DEFAULT, style);
        return view;
    }

    private GradientDrawable round(int fill, int radius, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radius));
        if (stroke != 0) {
            drawable.setStroke(dp(1), stroke);
        }
        return drawable;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
