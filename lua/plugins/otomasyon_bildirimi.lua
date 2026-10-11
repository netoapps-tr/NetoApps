-- NetOps automation notification plugin.
local key = "automation.count"

netops.on("automation.completed", function(payload)
    local id = tostring(payload.automation_id or "bilinmeyen")
    local count = netops.memory.get(key, 0)
    netops.memory.set(key, count + 1, "otomasyon_bildirimi")
    netops.notify("NetOps", "Otomasyon tamamlandı: " .. id .. " (toplam: " .. tostring(count + 1) .. ")")
end)

return {
    name = "Otomasyon Bildirimi",
    version = "1.0",
    description = "Otomasyon tamamlanınca bildirim ve çalışma sayacı oluşturur",
}