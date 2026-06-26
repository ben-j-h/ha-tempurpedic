"""UDP client for Tempurpedic adjustable base."""

from __future__ import annotations

import contextlib
import logging
import socket
import time

_LOGGER = logging.getLogger(__name__)


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
        VIB_POST is always sent once the session is open, even on failure,
        so the bed is never left with a dangling open session.
        """
        from .const import VIB_POST, VIB_PRE

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        session_open = False
        ok = False
        try:
            sock.settimeout(2)
            sock.connect((self._host, self._port))
            sock.send(VIB_PRE)
            try:
                ack5 = sock.recv(32)
            except TimeoutError:
                _LOGGER.warning("VIB_PRE timeout from %s (bed offline?)", self._host)
                return False
            session_open = True
            _LOGGER.debug("VIB session open; ACK5=%r", ack5)
            ok = True
            for cmd in commands:
                sock.send(cmd)
                try:
                    ack = sock.recv(16)
                except TimeoutError:
                    _LOGGER.warning("VIB command ACK timeout from %s", self._host)
                    ok = False
                    break
                if ack not in (b"ACK3", b"ACK\x03"):
                    _LOGGER.warning(
                        "VIB unexpected ACK from %s: %r (expected ACK3)",
                        self._host,
                        ack,
                    )
                    ok = False
                    break
        except OSError as e:
            _LOGGER.warning("VIB session OSError for %s: %s", self._host, e)
            ok = False
        finally:
            if session_open:
                with contextlib.suppress(OSError):
                    sock.send(VIB_POST)
                    with contextlib.suppress(OSError):
                        sock.recv(16)  # ACK4
            with contextlib.suppress(OSError):
                sock.close()
        return ok

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
