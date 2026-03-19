# AMB — Agent Message Bus

Peer-to-peer TCP mesh network for LLM agent collaboration. Designed for [Claude Code](https://claude.ai/code) multi-agent setups but works with any agent framework.

## Features

- **Peer-to-peer mesh** — no central server, agents communicate directly
- **<1ms delivery** — TCP direct connection between nodes
- **Persistent inbox** — messages survive agent restarts (JSONL logs)
- **Activity tracking** — see what each agent is working on
- **Challenge protocol** — agents are expected to disagree constructively
- **Background task tracking** — delegating agent launches a background monitor that tracks acknowledgment, deadline, and result delivery
- **Background AMB listener** — agent stays reachable during long tasks via a background listener that relays messages to the operator
- **Mandatory cross-review** — every change is reviewed by another agent before acceptance
- **Post-incident learning** — mistakes are analyzed for root cause and fed back into team knowledge
- **Claude Code integration** — auto-generated rules and skills for each agent

## How Agents Collaborate

```
                    Delegate task via AMB
CTO Agent ─────────────────────────────────────→ Dev Agent
    │                                                │
    │  launch background tracker                     │  launch background listener
    │  (polls for ack/result/deadline)               │  (relays AMB while working)
    │                                                │
    │← ack: "Accepted, starting." ──────────────────│
    │                                                │  ... working ...
    │← result: "Done: path/to/file" ────────────────│
    │                                                │
    │  send for cross-review ──→ R&D Agent           │
    │← review: "APPROVE / NEEDS CHANGES" ──────────│
    │                                                │
    │  close task on BOARD.md                        │
```

## Quick Start

```bash
# 1. Define your agent
cat > agents/my-agent.yaml << EOF
name: Alice
port: 15000
workspace: /home/user/alice-workspace
role: developer
EOF

# 2. Generate Claude Code configs
bash templates/setup.sh

# 3. Start your node
export AMB_NAME=Alice AMB_PORT=15000
amb start

# 4. Send a message
amb send --to Bob "ready for code review"

# 5. Check messages
amb recv
```

## Key Protocols

| Protocol | Purpose | See |
|----------|---------|-----|
| Task Delegation | Structured task format + mandatory background tracker | [PROTOCOL.md §Task Delegation](PROTOCOL.md#task-delegation-protocol) |
| Background Listener | Stay reachable during long tasks | [PROTOCOL.md §Background AMB Listener](PROTOCOL.md#background-amb-listener) |
| Cross-Review | Every change reviewed by another agent | [PROTOCOL.md §Cross-Review](PROTOCOL.md#cross-review-protocol) |
| Challenge Obligation | Agents MUST disagree constructively | [PROTOCOL.md §Communication Rules](PROTOCOL.md#communication-rules) |
| Team Learning | Post-incident root cause → lesson → prevention | [PROTOCOL.md §Team Learning](PROTOCOL.md#team-learning-protocol) |

## Repository Structure

```
├── PROTOCOL.md          # Full protocol specification (v5.0)
├── README.md            # This file
├── amb                  # CLI client (Python 3.8+)
├── amb_node.py          # TCP daemon (asyncio)
├── amb_listener.py      # Optional background subscriber
├── agents/              # Agent configs
│   └── example.yaml     # Example agent config
├── templates/           # Claude Code integration
│   ├── inter-agent.template.md   # Protocol rules template
│   ├── amb-relay.template.md     # Relay loop skill template
│   └── setup.sh                  # Config generator
├── examples/
│   └── hierarchy-team/  # Complete 3-agent example (CTO + Engineer + Analyst)
└── threads/             # Formal task threads (T001-T038+)
```

## Adding a New Agent

1. Create `agents/<name>.yaml` with name, port, workspace path
2. Run `bash templates/setup.sh`
3. Agent starts with `amb start` — automatically joins the mesh

See [PROTOCOL.md](PROTOCOL.md) for the full specification.

## Requirements

- Python 3.8+
- No external dependencies (stdlib only: asyncio, socket, json)
