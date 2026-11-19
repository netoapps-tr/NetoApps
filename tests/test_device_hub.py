from __future__ import annotations

from types import SimpleNamespace

from neto_device_hub import NetOpsDeviceHub


class _AliveThread:
    def is_alive(self) -> bool:
        return True


def _hub_with_server(sockets):
    hub = NetOpsDeviceHub.__new__(NetOpsDeviceHub)
    hub._thread = _AliveThread()
    hub._loop = object()
    hub._server = SimpleNamespace(sockets=sockets)
    return hub


def test_is_running_is_false_when_server_has_no_listening_sockets() -> None:
    assert not _hub_with_server([]).is_running()


def test_is_running_is_true_when_server_has_a_listening_socket() -> None:
    assert _hub_with_server([object()]).is_running()
