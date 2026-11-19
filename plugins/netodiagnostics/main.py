def register(api):
    api.register_panel("netodiagnostics", title="NetoDiagnostics", icon="diagnostics")
    return {"id": "netodiagnostics", "registered": True}
