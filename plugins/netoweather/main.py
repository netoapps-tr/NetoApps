def register(api):
    api.register_panel("netoweather", title="NetoWeather", icon="weather")
    return {"id": "netoweather", "registered": True}
