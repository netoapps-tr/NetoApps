def register(api):
    api.register_panel("netobackup", title="NetoBackup", icon="backup")
    return {"id": "netobackup", "registered": True}
