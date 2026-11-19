import unittest

from neto_plugin_api import NetOpsPluginAPI


class FakePermissions:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.seen = []

    def require(self, permission, context="", ask_callback=None):
        self.seen.append((permission, context))
        return self.allowed


class PluginApiTests(unittest.TestCase):
    def test_netopilot_actions_use_permission_boundary(self):
        permissions = FakePermissions()
        api = NetOpsPluginAPI(
            handlers={"system_status": lambda: {"cpu": 1}},
            permission_manager=permissions,
        )
        api.register_command("sistem durumu", "Durumu göster", "system_status", "netopilot")
        result = api.invoke("system_status")
        self.assertEqual(result["result"], {"cpu": 1})
        self.assertEqual(permissions.seen[0][0], "system_status")

    def test_denied_action_never_calls_handler(self):
        permissions = FakePermissions(allowed=False)
        called = []
        api = NetOpsPluginAPI(
            handlers={"launch_program": lambda name: called.append(name)},
            permission_manager=permissions,
        )
        result = api.invoke("launch_program", "notepad")
        self.assertFalse(result["ok"])
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
