-- NetOps Lua event hooks.
-- Add feature handlers here without changing the Python UI bridge.

netops.on("automation.started", function(payload)
    netops.log("Lua çekirdeği otomasyonu izliyor: " .. tostring(payload.automation_id or ""))
end)

return true