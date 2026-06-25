"""UDP client for Tempurpedic adjustable base."""

from __future__ import annotations

import socket
import time


class TempurpedicClient:
    """Sends commands to the Tempurpedic bed via UDP."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def send_command(self, command: bytes) -> bool:
        """Send a command using the three-step LOGICDATAOPEN protocol.

        Returns True if ACK3 received, False on timeout/error.
        """
        from .const import LOGICDATAOPEN

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.connect((self._host, self._port))

            sock.send(command)

            time.sleep(0.15)
            sock.send(LOGICDATAOPEN)
            try:
                sock.recv(16)
            except socket.timeout:
                pass

            time.sleep(0.15)
            sock.send(command)
            try:
                ack = sock.recv(16)
                return ack == b"ACK3"
            except socket.timeout:
                return False
        except OSError:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def test_connection(self) -> bool:
        """Quick connectivity test — send LOGICDATAOPEN and expect ACK\\xfe."""
        from .const import LOGICDATAOPEN

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.connect((self._host, self._port))
            sock.send(LOGICDATAOPEN)
            ack = sock.recv(16)
            return ack == b"ACK\xfe"
        except (OSError, socket.timeout):
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass
