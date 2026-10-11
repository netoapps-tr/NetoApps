package com.netops.mobile;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** Dependency-free WebSocket link for the local NetOps PC hub. */
final class NetOpsLinkClient {
    interface Listener {
        void onState(String state);
        void onHello(String deviceId, String token);
        void onMessage(JSONObject message);
        void onError(String message);
        void onDisconnected(String reason);
    }

    private static final int CONNECT_TIMEOUT_MS = 4500;
    private static final int READ_TIMEOUT_MS = 5000;
    private static final long HEARTBEAT_MS = 9000L;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final SecureRandom random = new SecureRandom();
    private final Listener listener;
    private volatile boolean running;
    private volatile boolean authenticationFailed;
    private volatile Socket socket;
    private volatile DataInputStream input;
    private volatile DataOutputStream output;
    private volatile String deviceId = "";
    private String address = "";
    private String storedDeviceId = "";
    private String storedToken = "";
    private String pairingCode = "";

    NetOpsLinkClient(Listener listener) {
        this.listener = listener;
    }

    void connect(DeviceStore.Device device) {
        disconnect();
        address = device.address;
        storedDeviceId = device.deviceId;
        storedToken = device.token;
        pairingCode = device.pairingCode;
        authenticationFailed = false;
        running = true;
        executor.execute(this::connectionLoop);
    }

    void disconnect() {
        running = false;
        closeSocket();
    }

    boolean isConnected() {
        return socket != null && deviceId != null && !deviceId.isEmpty();
    }

    void requestAssistant(String text) {
        JSONObject message = new JSONObject();
        try {
            message.put("type", "assistant_request");
            message.put("id", "android_" + UUID.randomUUID().toString().replace("-", ""));
            message.put("device_id", deviceId);
            message.put("text", text);
            sendJson(message);
        } catch (Exception error) {
            notifyError("İstek gönderilemedi.");
        }
    }

    void requestMedia(String action) {
        JSONObject message = new JSONObject();
        try {
            message.put("type", "media_request");
            message.put("id", "media_" + UUID.randomUUID().toString().replace("-", ""));
            message.put("device_id", deviceId);
            message.put("action", action);
            message.put("args", new JSONObject());
            sendJson(message);
        } catch (Exception error) {
            notifyError("Medya komutu gönderilemedi.");
        }
    }

    private void connectionLoop() {
        notifyState("Bağlanıyor...");
        while (running && !authenticationFailed) {
            try {
                openSocket();
                sendHello();
                readLoop();
            } catch (Exception error) {
                if (running && !authenticationFailed) {
                    notifyError(connectionError(error));
                }
            } finally {
                closeSocket();
                deviceId = "";
            }
            if (running && !authenticationFailed) {
                notifyState("Yeniden bağlanıyor...");
                sleepQuietly(2500L);
            }
        }
        if (running) {
            running = false;
        }
        notifyDisconnected(authenticationFailed ? "Eşleşme bilgisi geçersiz." : "Bağlantı kesildi.");
    }

    private void openSocket() throws Exception {
        URI uri = parseAddress(address);
        String scheme = uri.getScheme().toLowerCase();
        int port = uri.getPort() > 0 ? uri.getPort() : (scheme.equals("wss") ? 443 : 80);
        Socket created;
        if (scheme.equals("wss")) {
            created = (SSLSocket) SSLSocketFactory.getDefault().createSocket();
        } else if (scheme.equals("ws")) {
            created = new Socket();
        } else {
            throw new IOException("Sadece ws:// veya wss:// bağlantısı desteklenir.");
        }
        created.setKeepAlive(true);
        created.setTcpNoDelay(true);
        created.connect(new InetSocketAddress(uri.getHost(), port), CONNECT_TIMEOUT_MS);
        created.setSoTimeout(READ_TIMEOUT_MS);
        if (created instanceof SSLSocket) {
            ((SSLSocket) created).startHandshake();
        }
        DataInputStream newInput = new DataInputStream(created.getInputStream());
        DataOutputStream newOutput = new DataOutputStream(created.getOutputStream());
        performHandshake(uri, newInput, newOutput, scheme.equals("wss") ? 443 : 80);
        socket = created;
        input = newInput;
        output = newOutput;
    }

    private void performHandshake(URI uri, DataInputStream newInput, DataOutputStream newOutput, int defaultPort) throws Exception {
        byte[] nonce = new byte[16];
        random.nextBytes(nonce);
        String key = android.util.Base64.encodeToString(nonce, android.util.Base64.NO_WRAP);
        int port = uri.getPort() > 0 ? uri.getPort() : defaultPort;
        String hostHeader = uri.getHost() + (port == 80 || port == 443 ? "" : ":" + port);
        String path = uri.getRawPath();
        if (path == null || path.isEmpty()) {
            path = "/";
        }
        if (uri.getRawQuery() != null && !uri.getRawQuery().isEmpty()) {
            path += "?" + uri.getRawQuery();
        }
        String request = "GET " + path + " HTTP/1.1\r\n"
                + "Host: " + hostHeader + "\r\n"
                + "Upgrade: websocket\r\n"
                + "Connection: Upgrade\r\n"
                + "Sec-WebSocket-Key: " + key + "\r\n"
                + "Sec-WebSocket-Version: 13\r\n\r\n";
        newOutput.write(request.getBytes(StandardCharsets.US_ASCII));
        newOutput.flush();

        ByteArrayOutputStream response = new ByteArrayOutputStream();
        int previous = -1;
        int current;
        while (response.size() < 16384 && (current = newInput.read()) != -1) {
            response.write(current);
            if (previous == '\r' && current == '\n') {
                byte[] data = response.toByteArray();
                int length = data.length;
                if (length >= 4 && data[length - 4] == '\r' && data[length - 3] == '\n'
                        && data[length - 2] == '\r' && data[length - 1] == '\n') {
                    break;
                }
            }
            previous = current;
        }
        String header = response.toString(StandardCharsets.US_ASCII.name());
        if (!header.startsWith("HTTP/1.1 101") && !header.startsWith("HTTP/1.0 101")) {
            throw new IOException("WebSocket el sıkışması reddedildi.");
        }
    }

    private void sendHello() throws Exception {
        JSONObject hello = new JSONObject();
        hello.put("type", "hello");
        hello.put("device_name", android.os.Build.MODEL);
        hello.put("manufacturer", android.os.Build.MANUFACTURER);
        hello.put("model", android.os.Build.MODEL);
        hello.put("android_version", android.os.Build.VERSION.RELEASE);
        hello.put("sdk_int", android.os.Build.VERSION.SDK_INT);
        hello.put("agent_version", "1.39.0-mobile");
        hello.put("network", new JSONObject().put("type", "local_wifi"));
        if (!storedDeviceId.isEmpty() && !storedToken.isEmpty()) {
            hello.put("device_id", storedDeviceId);
            hello.put("token", storedToken);
        } else if (!pairingCode.isEmpty()) {
            hello.put("pairing_code", pairingCode);
        }
        sendJson(hello);
    }

    private void readLoop() throws Exception {
        long nextHeartbeat = System.currentTimeMillis() + HEARTBEAT_MS;
        while (running && socket != null && !socket.isClosed()) {
            Frame frame;
            try {
                frame = readFrame();
            } catch (java.net.SocketTimeoutException timeout) {
                frame = null;
            }
            if (frame != null) {
                if (frame.opcode == 8) {
                    return;
                }
                if (frame.opcode == 9) {
                    sendFrame(10, frame.payload);
                } else if (frame.opcode == 1) {
                    handleText(new String(frame.payload, StandardCharsets.UTF_8));
                }
            }
            if (System.currentTimeMillis() >= nextHeartbeat && !deviceId.isEmpty()) {
                JSONObject heartbeat = new JSONObject();
                heartbeat.put("type", "heartbeat");
                heartbeat.put("device_id", deviceId);
                sendJson(heartbeat);
                nextHeartbeat = System.currentTimeMillis() + HEARTBEAT_MS;
            }
        }
    }

    private void handleText(String text) {
        try {
            JSONObject message = new JSONObject(text);
            String type = message.optString("type", "");
            if ("hello_result".equals(type)) {
                if (!message.optBoolean("ok", false)) {
                    authenticationFailed = true;
                    notifyError(helloError(message.optString("error", "PAIRING_REQUIRED")));
                    return;
                }
                deviceId = message.optString("device_id", "");
                String token = message.optString("token", "");
                notifyState("Bağlandı");
                notifyHello(deviceId, token);
            }
            notifyMessage(message);
        } catch (Exception error) {
            notifyError("PC yanıtı okunamadı.");
        }
    }

    private Frame readFrame() throws IOException {
        DataInputStream stream = input;
        if (stream == null) {
            throw new IOException("Akış hazır değil.");
        }
        int first = stream.readUnsignedByte();
        int second = stream.readUnsignedByte();
        int opcode = first & 0x0f;
        long length = second & 0x7f;
        if (length == 126) {
            length = stream.readUnsignedShort();
        } else if (length == 127) {
            length = stream.readLong();
            if (length < 0 || length > 1024 * 1024) {
                throw new IOException("WebSocket mesajı çok büyük.");
            }
        }
        boolean masked = (second & 0x80) != 0;
        byte[] mask = masked ? readBytes(stream, 4) : null;
        byte[] payload = readBytes(stream, (int) length);
        if (masked) {
            for (int i = 0; i < payload.length; i++) {
                payload[i] = (byte) (payload[i] ^ mask[i % 4]);
            }
        }
        return new Frame(opcode, payload);
    }

    private void sendJson(JSONObject message) throws Exception {
        sendFrame(1, message.toString().getBytes(StandardCharsets.UTF_8));
    }

    private synchronized void sendFrame(int opcode, byte[] payload) throws IOException {
        DataOutputStream stream = output;
        if (stream == null || socket == null || socket.isClosed()) {
            throw new IOException("PC bağlı değil.");
        }
        int length = payload.length;
        stream.writeByte(0x80 | opcode);
        if (length < 126) {
            stream.writeByte(0x80 | length);
        } else if (length <= 65535) {
            stream.writeByte(0x80 | 126);
            stream.writeShort(length);
        } else {
            stream.writeByte(0x80 | 127);
            stream.writeLong(length);
        }
        byte[] mask = new byte[4];
        random.nextBytes(mask);
        stream.write(mask);
        for (int i = 0; i < payload.length; i++) {
            stream.writeByte(payload[i] ^ mask[i % 4]);
        }
        stream.flush();
    }

    private URI parseAddress(String value) throws Exception {
        String cleaned = value == null ? "" : value.trim();
        if (!cleaned.contains("://")) {
            cleaned = "ws://" + cleaned;
        }
        URI uri = URI.create(cleaned);
        if (uri.getHost() == null || uri.getHost().isEmpty()) {
            throw new UnknownHostException("PC adresi bulunamadı.");
        }
        return uri;
    }

    private void closeSocket() {
        Socket current = socket;
        socket = null;
        input = null;
        output = null;
        if (current != null) {
            try {
                current.close();
            } catch (Exception ignored) {
            }
        }
    }

    private byte[] readBytes(DataInputStream stream, int length) throws IOException {
        byte[] data = new byte[length];
        stream.readFully(data);
        return data;
    }

    private void notifyState(String state) {
        listener.onState(state);
    }

    private void notifyHello(String id, String token) {
        listener.onHello(id, token);
    }

    private void notifyMessage(JSONObject message) {
        listener.onMessage(message);
    }

    private void notifyError(String error) {
        listener.onError(error);
    }

    private void notifyDisconnected(String reason) {
        listener.onDisconnected(reason);
    }

    private String connectionError(Exception error) {
        if (error instanceof UnknownHostException) {
            return "PC adresi bulunamadı.";
        }
        return "PC bağlantısı kurulamadı.";
    }

    private String helloError(String error) {
        if ("INVALID_PAIRING_CODE".equals(error)) {
            return "Eşleştirme kodu geçersiz veya süresi dolmuş.";
        }
        if ("PAIRING_REQUIRED".equals(error)) {
            return "Bu cihaz henüz PC ile eşleştirilmemiş.";
        }
        return "Cihaz doğrulanamadı.";
    }

    private void sleepQuietly(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
    }

    private static final class Frame {
        final int opcode;
        final byte[] payload;

        Frame(int opcode, byte[] payload) {
            this.opcode = opcode;
            this.payload = payload;
        }
    }
}
