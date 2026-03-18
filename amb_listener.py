#!/usr/bin/env python3
"""
AMB persistent listener — runs as a background subagent.

Connects to own AMB node, subscribes to live messages,
writes each incoming message to an INBOX FILE that the
main agent checks periodically.

Usage (from Agent tool, run_in_background=true):
    python3 amb_listener.py --name AgentName --port 15000

The listener:
  1. Connects to local AMB node (subscribe mode)
  2. Each incoming message → appended to bus/{name}_inbox.jsonl
  3. Prints message to stdout (captured by Agent tool on completion)
  4. Runs FOREVER until killed

The main agent reads bus/{name}_inbox.jsonl between tasks.
"""
import json
import os
import socket
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.environ.get("AMB_BUS_DIR", os.path.join(_SCRIPT_DIR, "bus"))


def inbox_file(name):
    return os.path.join(BUS_DIR, f"{name}_inbox.jsonl")


def cursor_file(name):
    return os.path.join(BUS_DIR, f"{name}_cursor")


def send_pkt(sock, obj):
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    sock.sendall(line.encode("utf-8"))


def format_msg(pkt):
    ts = pkt.get("ts", 0)
    t = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "??:??:??"
    frm = pkt.get("from", "?")
    body = pkt.get("body", "")
    return f"[{t}] {frm}: {body}"


def run_listener(name, port, host="127.0.0.1"):
    os.makedirs(BUS_DIR, exist_ok=True)
    ifile = inbox_file(name)

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))

            # Subscribe
            send_pkt(sock, {"op": "subscribe"})
            print(f"[AMB-listener] Connected to {name}@{host}:{port}, listening...",
                  file=sys.stderr, flush=True)

            sock.settimeout(None)  # block forever
            buf = b""

            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    print("[AMB-listener] Connection lost, reconnecting...",
                          file=sys.stderr, flush=True)
                    break

                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        pkt = json.loads(line.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue

                    op = pkt.get("op")
                    if op == "subscribed":
                        continue
                    if op == "msg":
                        # Write to inbox file
                        with open(ifile, "a") as f:
                            f.write(json.dumps(pkt, ensure_ascii=False) + "\n")

                        # Print to stdout (main agent sees on completion)
                        formatted = format_msg(pkt)
                        print(formatted, flush=True)

            sock.close()

        except (ConnectionError, OSError) as e:
            print(f"[AMB-listener] Connection error: {e}, retrying in 3s...",
                  file=sys.stderr, flush=True)

        time.sleep(3)  # reconnect backoff


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    run_listener(args.name, args.port, args.host)
