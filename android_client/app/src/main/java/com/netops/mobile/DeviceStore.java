package com.netops.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Small encrypted device registry kept entirely on the Android device. */
final class DeviceStore {
    private static final String PREFS = "netops_devices";
    private static final String DEVICES = "devices";
    private static final String KEY_ALIAS = "netops_device_tokens";

    static final class Device {
        String name;
        String address;
        String deviceId;
        String token;
        String pairingCode;

        Device(String name, String address, String deviceId, String token, String pairingCode) {
            this.name = clean(name, "NetOps PC");
            this.address = clean(address, "");
            this.deviceId = clean(deviceId, "");
            this.token = clean(token, "");
            this.pairingCode = clean(pairingCode, "");
        }

        String displayName() {
            return name.isEmpty() ? "NetOps PC" : name;
        }
    }

    private final SharedPreferences preferences;

    DeviceStore(Context context) {
        preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    synchronized List<Device> load() {
        ArrayList<Device> devices = new ArrayList<>();
        String raw = preferences.getString(DEVICES, "[]");
        try {
            JSONArray array = new JSONArray(raw);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.optJSONObject(i);
                if (item == null) {
                    continue;
                }
                String encryptedToken = item.optString("token", "");
                String token = decrypt(encryptedToken);
                devices.add(new Device(
                        item.optString("name", "NetOps PC"),
                        item.optString("address", ""),
                        item.optString("device_id", ""),
                        token,
                        item.optString("pairing_code", "")
                ));
            }
        } catch (Exception ignored) {
            // A corrupt local registry must not prevent the app from opening.
        }
        return devices;
    }

    synchronized void upsert(Device device) {
        ArrayList<Device> devices = new ArrayList<>(load());
        boolean replaced = false;
        for (int i = 0; i < devices.size(); i++) {
            Device current = devices.get(i);
            boolean same = !device.deviceId.isEmpty() && device.deviceId.equals(current.deviceId)
                    || device.address.equalsIgnoreCase(current.address);
            if (same) {
                devices.set(i, device);
                replaced = true;
                break;
            }
        }
        if (!replaced) {
            devices.add(device);
        }
        save(devices);
    }

    synchronized void remove(Device target) {
        ArrayList<Device> devices = new ArrayList<>(load());
        devices.removeIf(device -> (!target.deviceId.isEmpty() && target.deviceId.equals(device.deviceId))
                || target.address.equalsIgnoreCase(device.address));
        save(devices);
    }

    private void save(List<Device> devices) {
        JSONArray array = new JSONArray();
        try {
            for (Device device : devices) {
                JSONObject item = new JSONObject();
                item.put("name", device.displayName());
                item.put("address", device.address);
                item.put("device_id", device.deviceId);
                item.put("token", encrypt(device.token));
                item.put("pairing_code", device.pairingCode);
                array.put(item);
            }
        } catch (Exception ignored) {
            return;
        }
        preferences.edit().putString(DEVICES, array.toString()).apply();
    }

    private String encrypt(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        try {
            SecretKey key = getKey();
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key);
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            byte[] iv = cipher.getIV();
            return Base64.encodeToString(iv, Base64.NO_WRAP) + ":"
                    + Base64.encodeToString(encrypted, Base64.NO_WRAP);
        } catch (Exception ignored) {
            return value;
        }
    }

    private String decrypt(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        try {
            String[] parts = value.split(":", 2);
            if (parts.length != 2) {
                return value;
            }
            byte[] iv = Base64.decode(parts[0], Base64.NO_WRAP);
            byte[] encrypted = Base64.decode(parts[1], Base64.NO_WRAP);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getKey(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return value;
        }
    }

    private SecretKey getKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build());
        return generator.generateKey();
    }

    private static String clean(String value, String fallback) {
        String cleaned = value == null ? "" : value.trim();
        return cleaned.isEmpty() ? fallback : cleaned;
    }
}
