import socket
import time

UDP_IP = "192.168.1.233"
UDP_PORT = 50007

# Protocol discovered via PCAPdroid capture (ergo.pcap):
#   1. Send 9-byte command
#   2. Wait ~150ms, send \xfeLOGICDATAOPEN (session keepalive, 14 bytes)
#   3. Wait ~150ms, send 9-byte command again
# Bed responds: ACK\xfe to LOGICDATAOPEN, ACK3 to commands.
# 0x35 / 0x34 are background heartbeats the app sends on separate sockets
# and are NOT required before commands.

LOGICDATAOPEN = b"\xfeLOGICDATAOPEN"

# 9-byte commands — from user-supplied hex, verified against PCAP
FLAT       = bytes.fromhex("3305320a945c0400cc")  # confirmed in ergo.pcap
HEAD_UP    = bytes.fromhex("3305321894530005c2")
HEAD_DOWN  = bytes.fromhex("3305321894540005c5")  # confirmed in ergo.pcap
LEGS_UP    = bytes.fromhex("3305321894510100c4")
LEGS_DOWN  = bytes.fromhex("3305321894520100c7")
PRESET_1   = bytes.fromhex("33053203945c0000c8")
PRESET_2   = bytes.fromhex("33053203945c0100c9")
PRESET_3   = bytes.fromhex("33053203945c0200ca")
PRESET_4   = bytes.fromhex("33053203945c0300cb")
VIB_OFF    = bytes.fromhex("3305320a9486000012")  # \x33\x05\x32\x0A\x94\x86\x00\x00\x12
VIB_1      = bytes.fromhex("33053203948d007861")
VIB_2      = bytes.fromhex("33053203948d017860")
VIB_3      = bytes.fromhex("33053203948d027863")
VIB_4      = bytes.fromhex("33053203948d037862")


def send_command(cmd_bytes):
    """Send a command using the protocol sequence from PCAP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    sock.connect((UDP_IP, UDP_PORT))

    sock.send(cmd_bytes)
    print(f"  [1] sent: {cmd_bytes.hex()}")

    time.sleep(0.15)
    sock.send(LOGICDATAOPEN)
    try:
        ack = sock.recv(16)
        print(f"  [2] LOGICDATAOPEN ack: {ack}")
    except socket.timeout:
        print("  [2] LOGICDATAOPEN: no ack")

    time.sleep(0.15)
    sock.send(cmd_bytes)
    try:
        ack = sock.recv(16)
        print(f"  [3] command ack: {ack}")
    except socket.timeout:
        print("  [3] command: no ack")

    sock.close()


print("=== Sending FLAT command ===")
send_command(FLAT)
