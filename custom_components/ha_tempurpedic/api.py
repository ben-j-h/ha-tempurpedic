"""UDP client for Tempurpedic adjustable base."""

from __future__ import annotations

import contextlib
import socket
import time


class TempurpedicClient:
    """Sends commands to the Tempurpedic bed via UDP."""

    def __init__(self, host: str, port: int) -> None:
        """Store connection parameters."""
        self._host = host
        self._port = port

    def send_command(self, command: bytes) -> bool:
        """
        Send a command using the three-step LOGICDATAOPEN protocol.

        Returns True if ACK3 received, False on timeout/error.
        """
        from .const import LOGICDATAOPEN

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(2)
            sock.connect((self._host, self._port))

            sock.send(command)

            time.sleep(0.15)
            sock.send(LOGICDATAOPEN)
            with contextlib.suppress(TimeoutError):
                sock.recv(16)

            time.sleep(0.15)
            sock.send(command)
            try:
                ack = sock.recv(16)
            except TimeoutError:
                return False
            else:
                return ack == b"ACK3"
        except OSError:
            return False
        finally:
            with contextlib.suppress(OSError):
                sock.close()

    def send_vib_session(self, commands: list[bytes]) -> bool:
        """
        Send one or more vibration commands in a PRE/POST session.

        Protocol: 0x35 → ACK5 → [command → ACK3]+ → 0x34 → ACK4.
        Multiple commands share one session (used for level stepping).
        """
        from .const import VIB_POST, VIB_PRE

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(2)
            sock.connect((self._host, self._port))
            sock.send(VIB_PRE)
            try:
                sock.recv(32)  # ACK5
            except TimeoutError:
                return False
            for cmd in commands:
                sock.send(cmd)
                try:
                    ack = sock.recv(16)
                except TimeoutError:
                    return False
                if ack != b"ACK3":
                    return False
            sock.send(VIB_POST)
            with contextlib.suppress(TimeoutError):
                sock.recv(16)  # ACK4
            return True
        except OSError:
            return False
        else:
            return True
        finally:
            with contextlib.suppress(OSError):
                sock.close()

    def send_command_direct(self, command: bytes) -> bool:
        """Single vibration command in a PRE/POST session."""
        return self.send_vib_session([command])

    def test_connection(self) -> bool:
        r"""Quick connectivity test -- send LOGICDATAOPEN and expect ACK\xfe."""
        from .const import LOGICDATAOPEN

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(3)
            sock.connect((self._host, self._port))
            sock.send(LOGICDATAOPEN)
            try:
                ack = sock.recv(16)
            except TimeoutError:
                return False
            else:
                return ack == b"ACK\xfe"
        except OSError:
            return False
        finally:
            with contextlib.suppress(OSError):
                sock.close()
