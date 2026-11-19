def register(api):
    api.register_panel("netoupdater", title="NetoUpdater", icon="update")
    return {"id": "netoupdater", "registered": True}
