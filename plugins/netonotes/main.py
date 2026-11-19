def register(api):
    api.register_panel("netonotes", title="NetoNotes", icon="notes")
    return {"id": "netonotes", "registered": True}
