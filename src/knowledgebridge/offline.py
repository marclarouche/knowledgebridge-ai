"""Process-scoped Python socket audit guard for reproducible offline verification."""

import sys


class OfflineGuard:
    """Irreversible for this process; permits only literal local Ollama connections.

    This is verification instrumentation, not an OS firewall or native-code sandbox.
    It cannot constrain the separate Ollama server process.
    """

    def __init__(self, port: int):
        self.port = port
        self.allowed_connections = 0
        self.blocked_events = 0

    def install(self) -> None:
        sys.addaudithook(self.audit)

    def audit(self, event: str, args: tuple[object, ...]) -> None:
        if event == "socket.connect":
            address = args[1]
            if (
                isinstance(address, tuple)
                and len(address) >= 2
                and address[0] in ("127.0.0.1", "::1")
                and address[1] == self.port
            ):
                self.allowed_connections += 1
                return
            self.blocked_events += 1
            raise OSError("Offline verification blocked a non-Ollama connection")
        if event == "socket.getaddrinfo" and args[0] not in ("127.0.0.1", "::1"):
            self.blocked_events += 1
            raise OSError("Offline verification blocked external name resolution")
