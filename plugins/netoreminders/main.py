def register(api):
    api.register_panel("netoreminders", title="NetoReminders", icon="reminder")
    return {"id": "netoreminders", "registered": True}
