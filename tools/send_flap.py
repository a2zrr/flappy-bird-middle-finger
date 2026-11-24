#!/usr/bin/env python3
"""Send FLAP (or a STATUS line) to the game over UDP, to test it without a camera.

Examples:
  python3 tools/send_flap.py                 # one flap
  python3 tools/send_flap.py --count 5       # five flaps, 0.6 s apart
  python3 tools/send_flap.py --status "hand=1 gesture=1"   # set the HUD to "finger UP"
"""

import argparse
import socket
import time


def main():
    p = argparse.ArgumentParser(description="Send FLAP messages to the Flappy Bird game.")
    p.add_argument("--port", type=int, default=5005, help="game UDP port (default 5005)")
    p.add_argument("--count", type=int, default=1, help="how many FLAPs to send (default 1)")
    p.add_argument("--gap", type=float, default=0.6, help="seconds between FLAPs (default 0.6)")
    p.add_argument("--status", metavar="FIELDS",
                   help='send one STATUS line instead, e.g. "hand=1 gesture=0"')
    args = p.parse_args()

    message = f"STATUS {args.status}" if args.status else "FLAP"
    target = ("127.0.0.1", args.port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for i in range(args.count):
            sock.sendto(message.encode("ascii"), target)
            print(f"sent {message!r} to {target[0]}:{target[1]}")
            if i + 1 < args.count:
                time.sleep(args.gap)


if __name__ == "__main__":
    main()
