#!/usr/bin/env python3
"""
AMB Node — персональный узел агента в mesh-сети.

Каждый агент запускает свой узел. Узлы общаются напрямую (peer-to-peer).
Нет центрального сервера. Каждый узел:
  - Слушает свой порт (принимает сообщения от других)
  - Хранит входящие в локальный лог
  - Пушит сообщения подписчику (свой агент) в реальном времени

Запуск:
    python3 amb_node.py --name Alice --port 15000

Протокол (TCP, line-delimited JSON):

  Входящее от другого агента:
    → {"op":"deliver","from":"Bob","id":"abc","body":"текст","ts":1710460800}
    ← {"op":"ack","id":"abc"}

  Свой агент читает:
    → {"op":"subscribe"}
    ← {"op":"msg",...}  (пуш в реальном времени, бесконечно)

  Свой агент забирает очередь:
    → {"op":"read"}
    ← {"op":"msg",...}  (все непрочитанные)
    ← {"op":"read_end","count":N}

  Своему агенту: кто в сети?
    → {"op":"peers"}
    ← {"op":"peers_result","peers":{...}}

  Регистрация пира:
    → {"op":"register","name":"Bob","host":"192.168.1.11","port":15001}
    ← {"op":"registered"}
"""
import asyncio
import json
import os
import sys
import time
import argparse
from typing import Optional, Dict, List

# ── Paths ───────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUS_DIR = os.environ.get("AMB_BUS_DIR", os.path.join(_SCRIPT_DIR, "bus"))
PEERS_FILE = os.environ.get("AMB_PEERS_FILE",
                             os.path.join(_SCRIPT_DIR, "peers.json"))

# ── State ───────────────────────────────────────────────────────

inbox = []               # all received messages (list of dict)
read_cursor = 0                  # what the agent has read
subscriber = None                # live push connection (Optional[StreamWriter])
node_name = ""
node_port = 0

# Heartbeat tracking
HEARTBEAT_INTERVAL = 30          # seconds between heartbeats
HEARTBEAT_TIMEOUT = 90           # seconds before peer considered dead
SUBSCRIBER_HEARTBEAT_INTERVAL = 60  # seconds between subscriber keepalive
peer_last_seen = {}              # name → timestamp (float)
peer_activity = {}               # name → {"text": str, "ts": float}
node_start_time = 0.0

# Own activity
current_activity = "idle"
activity_ts = 0.0
activity_log = []  # list of {"text": str, "ts": float} — last N activities
MAX_ACTIVITY_LOG = 20


def log_file():
    return os.path.join(BUS_DIR, f"{node_name}.jsonl")


# ── Persistence ─────────────────────────────────────────────────

def load_inbox():
    global inbox, read_cursor
    path = log_file()
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    inbox.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    # Mark all persisted messages as already read — no replay of history
    read_cursor = len(inbox)
    print(f"[{node_name}] Loaded {len(inbox)} messages from log (cursor at end)")


def append_log(msg):
    with open(log_file(), "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def inbox_file():
    return os.path.join(BUS_DIR, f"{node_name}_inbox.jsonl")


def append_inbox(msg):
    """Write to _inbox.jsonl for offline reading by `amb check`."""
    entry = {"op": "msg", **msg}
    with open(inbox_file(), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Peers ───────────────────────────────────────────────────────

def load_peers():
    if not os.path.exists(PEERS_FILE):
        return {}
    try:
        with open(PEERS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_peers(peers):
    tmp = PEERS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(peers, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PEERS_FILE)


def register_self(host):
    """Register this node in the peers file."""
    peers = load_peers()
    peers[node_name] = {"host": host, "port": node_port}
    save_peers(peers)
    print(f"[{node_name}] Registered as {host}:{node_port}")


def unregister_self():
    """Remove this node from peers file."""
    peers = load_peers()
    peers.pop(node_name, None)
    save_peers(peers)


# ── Send JSON helper ────────────────────────────────────────────

async def send_json(writer, obj):
    try:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        writer.write(line.encode("utf-8"))
        await writer.drain()
        return True
    except (ConnectionError, OSError, asyncio.CancelledError):
        return False


# ── Push to subscriber ──────────────────────────────────────────

async def push_to_subscriber(msg):
    """Push a message to the live subscriber (if connected)."""
    global subscriber, read_cursor
    if subscriber is None:
        return
    ok = await send_json(subscriber, {"op": "msg", **msg})
    if ok:
        read_cursor = len(inbox)
    else:
        subscriber = None


# ── Client handler ──────────────────────────────────────────────

async def handle_connection(reader, writer):
    global current_activity, activity_ts
    global subscriber, read_cursor
    addr = writer.get_extra_info("peername")

    try:
        while True:
            raw = await reader.readline()
            if not raw:
                break

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                pkt = json.loads(line)
            except json.JSONDecodeError:
                await send_json(writer, {"op": "error", "msg": "bad json"})
                continue

            op = pkt.get("op")

            # ── DELIVER: incoming message from another agent ──
            if op == "deliver":
                msg = {
                    "id": pkt.get("id", "?"),
                    "from": pkt.get("from", "?"),
                    "to": node_name,
                    "ts": pkt.get("ts", time.time()),
                    "body": pkt.get("body", ""),
                }
                inbox.append(msg)
                append_log(msg)
                append_inbox(msg)
                await send_json(writer, {"op": "ack", "id": msg["id"]})
                print(f"[{node_name}] ← {msg['from']}: "
                      f"{msg['body'][:80]}{'...' if len(msg['body']) > 80 else ''}")
                # Push to subscriber immediately
                await push_to_subscriber(msg)

            # ── SUBSCRIBE: agent wants live push ──
            elif op == "subscribe":
                subscriber = writer
                # Compute backlog BEFORE shifting cursor
                backlog = max(0, len(inbox) - read_cursor)
                # Send unread first
                for msg in inbox[read_cursor:]:
                    await send_json(writer, {"op": "msg", **msg})
                read_cursor = len(inbox)
                await send_json(writer, {"op": "subscribed",
                                          "backlog": backlog})
                print(f"[{node_name}] Agent subscribed for live push")
                # Keep connection open — don't break, let readline block
                # When a new message arrives, push_to_subscriber sends it
                # We just keep reading (agent might send ack or unsubscribe)
                continue

            # ── READ: agent wants queued messages (non-blocking) ──
            elif op == "read":
                pending = inbox[read_cursor:]
                for msg in pending:
                    await send_json(writer, {"op": "msg", **msg})
                read_cursor = len(inbox)
                await send_json(writer, {"op": "read_end",
                                          "count": len(pending)})

            # ── PEERS: who's in the network? ──
            elif op == "peers":
                peers = load_peers()
                await send_json(writer, {"op": "peers_result",
                                          "peers": peers})

            # ── REGISTER: another node announces itself ──
            elif op == "register":
                name = pkt.get("name", "?")
                host = pkt.get("host", "127.0.0.1")
                port = pkt.get("port", 0)
                peers = load_peers()
                peers[name] = {"host": host, "port": port}
                save_peers(peers)
                await send_json(writer, {"op": "registered"})
                print(f"[{node_name}] Registered peer: {name} @ {host}:{port}")

            # ── PEEK: unread count without consuming ──
            elif op == "peek":
                unread = max(0, len(inbox) - read_cursor)
                last_from = inbox[-1].get("from", "") if inbox else ""
                await send_json(writer, {
                    "op": "peek_result",
                    "unread": unread,
                    "last_from": last_from,
                    "total": len(inbox),
                })

            # ── PING: health check ──
            elif op == "ping":
                await send_json(writer, {"op": "pong",
                                          "name": node_name,
                                          "inbox_size": len(inbox),
                                          "ts": time.time()})

            # ── HEARTBEAT: peer liveness + activity exchange ──
            elif op == "heartbeat":
                sender = pkt.get("name", "?")
                peer_last_seen[sender] = time.time()
                # Store peer's activity
                if "activity" in pkt:
                    peer_activity[sender] = {
                        "text": pkt["activity"],
                        "ts": pkt.get("activity_ts", time.time()),
                    }
                await send_json(writer, {
                    "op": "heartbeat_ack",
                    "name": node_name,
                    "ts": time.time(),
                    "activity": current_activity,
                    "activity_ts": activity_ts,
                })

            # ── SET_ACTIVITY: agent reports what it's doing ──
            elif op == "set_activity":
                current_activity = pkt.get("text", "idle")
                activity_ts = time.time()
                activity_log.append({"text": current_activity, "ts": activity_ts})
                if len(activity_log) > MAX_ACTIVITY_LOG:
                    activity_log.pop(0)
                await send_json(writer, {"op": "ack_activity",
                                          "text": current_activity,
                                          "ts": activity_ts})

            # ── STATUS: full node status with peer health + activity ──
            elif op == "status":
                now = time.time()
                peer_info = {}
                peers = load_peers()
                for pname in peers:
                    if pname == node_name:
                        peer_info[pname] = {
                            "status": "self",
                            "activity": current_activity,
                            "activity_age": int(now - activity_ts) if activity_ts > 0 else 0,
                        }
                    elif pname in peer_last_seen:
                        age = now - peer_last_seen[pname]
                        alive = age < HEARTBEAT_TIMEOUT
                        act = peer_activity.get(pname, {})
                        act_text = act.get("text", "?")
                        act_age = int(now - act.get("ts", 0)) if act.get("ts", 0) > 0 else 0
                        peer_info[pname] = {
                            "status": "alive" if alive else "DEAD",
                            "last_seen": int(age),
                            "activity": act_text,
                            "activity_age": act_age,
                        }
                    else:
                        peer_info[pname] = {"status": "unknown", "activity": "?"}
                await send_json(writer, {
                    "op": "status_result",
                    "name": node_name,
                    "inbox_size": len(inbox),
                    "subscriber": subscriber is not None,
                    "activity": current_activity,
                    "activity_log": activity_log[-5:],
                    "uptime": now - node_start_time,
                    "peers": peer_info,
                })

            else:
                await send_json(writer, {"op": "error",
                                          "msg": f"unknown op: {op}"})

    except (ConnectionError, asyncio.CancelledError,
            asyncio.IncompleteReadError):
        pass
    finally:
        if writer is subscriber:
            subscriber = None
            print(f"[{node_name}] Subscriber disconnected")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ── Announce to existing peers ──────────────────────────────────

async def announce_to_peers(host):
    """Tell all known peers about this node."""
    peers = load_peers()
    for name, info in peers.items():
        if name == node_name:
            continue
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(info["host"], info["port"]),
                timeout=2
            )
            pkt = {"op": "register", "name": node_name,
                   "host": host, "port": node_port}
            w.write((json.dumps(pkt) + "\n").encode())
            await w.drain()
            resp_raw = await asyncio.wait_for(r.readline(), timeout=2)
            w.close()
            await w.wait_closed()
            print(f"[{node_name}] Announced to {name}")
        except Exception:
            pass  # Peer offline — fine


# ── Main ────────────────────────────────────────────────────────

async def main():
    global node_name, node_port

    parser = argparse.ArgumentParser(description="AMB Node")
    parser.add_argument("--name", required=True, help="Agent name")
    parser.add_argument("--port", type=int, required=True, help="Listen port")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default: 127.0.0.1, loopback only)")
    parser.add_argument("--announce-host", default="127.0.0.1",
                        help="Host to advertise to peers (default: 127.0.0.1)")
    args = parser.parse_args()

    node_name = args.name
    node_port = args.port

    os.makedirs(BUS_DIR, exist_ok=True)
    load_inbox()
    register_self(args.announce_host)

    server = await asyncio.start_server(
        handle_connection, args.host, args.port
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"[{node_name}] Node listening on {addrs}")
    print(f"[{node_name}] Log: {log_file()}")

    # Announce to known peers
    await announce_to_peers(args.announce_host)

    # Start heartbeat background tasks
    asyncio.ensure_future(heartbeat_loop())
    asyncio.ensure_future(subscriber_heartbeat_loop())

    try:
        async with server:
            await server.serve_forever()
    finally:
        unregister_self()


async def subscriber_heartbeat_loop():
    """Send periodic heartbeat to subscriber to detect dead connections."""
    global subscriber
    while True:
        await asyncio.sleep(SUBSCRIBER_HEARTBEAT_INTERVAL)
        if subscriber is not None:
            ok = await send_json(subscriber, {
                "op": "heartbeat_sub", "ts": time.time(),
            })
            if not ok:
                subscriber = None
                print(f"[{node_name}] Subscriber dead (heartbeat failed)")


async def heartbeat_loop():
    """Send heartbeat to all peers every HEARTBEAT_INTERVAL seconds."""
    global node_start_time
    node_start_time = time.time()

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        peers = load_peers()
        now = time.time()

        for name, info in peers.items():
            if name == node_name:
                continue
            try:
                r, w = await asyncio.wait_for(
                    asyncio.open_connection(info["host"], info["port"]),
                    timeout=3
                )
                pkt = {"op": "heartbeat", "name": node_name, "ts": now,
                       "activity": current_activity, "activity_ts": activity_ts}
                w.write((json.dumps(pkt) + "\n").encode())
                await w.drain()
                resp_raw = await asyncio.wait_for(r.readline(), timeout=3)
                if resp_raw:
                    resp = json.loads(resp_raw.decode())
                    if resp.get("op") == "heartbeat_ack":
                        peer_last_seen[name] = now
                        if "activity" in resp:
                            peer_activity[name] = {
                                "text": resp["activity"],
                                "ts": resp.get("activity_ts", now),
                            }
                w.close()
                await w.wait_closed()
            except Exception:
                # Peer unreachable — check if dead
                last = peer_last_seen.get(name, 0)
                if last > 0 and (now - last) > HEARTBEAT_TIMEOUT:
                    print(f"[{node_name}] ⚠ Peer {name} DEAD "
                          f"(last seen {int(now - last)}s ago)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{node_name}] Shutting down")
        unregister_self()
