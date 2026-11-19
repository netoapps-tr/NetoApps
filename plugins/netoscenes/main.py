def register(api):
    api.register_panel("netoscenes", title="NetoScenes", icon="scene")
    return {"id": "netoscenes", "registered": True}
