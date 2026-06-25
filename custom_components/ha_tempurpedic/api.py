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

    def send_command_direct(self, command: bytes) -> bool:
        """
        Send a single packet and expect ACK3, no LOGICDATAOPEN.

        Vibration commands don't use the session protocol.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(2)
            sock.connect((self._host, self._port))
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
