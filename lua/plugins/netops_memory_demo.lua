-- Example plugin: persistent memory is available to every Lua extension.
local key = "plugin.netops_memory_demo.loaded"
local count = netops.memory.get(key, 0)
netops.memory.set(key, count + 1, "netops_memory_demo")

netops.on("automation.completed", function(payload)
    netops.log("Memory demo eklentisi otomasyonu izledi: " .. tostring(payload.automation_id or ""))
end)

return {
    name = "NetOps Memory Demo",
    version = "1.0",
    description = "Lua hafızasının ve eklenti yaşam döngüsünün örnek kullanımı",
}