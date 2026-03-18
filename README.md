# AMB — Agent Message Bus

Peer-to-peer TCP mesh network for LLM agent collaboration. Designed for [Claude Code](https://claude.ai/code) multi-agent setups but works with any agent framework.

## Features

- **Peer-to-peer mesh** — no central server, agents communicate directly
- **<1ms delivery** — TCP direct connection between nodes
- **Persistent inbox** — messages survive agent restarts (JSONL logs)
- **Activity tracking** — see what each agent is working on
- **Challenge protocol** — agents are expected to disagree constructively
- **Task watcher** — background monitoring of delegated tasks
- **Claude Code integration** — auto-generated rules and skills for each agent

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

## Repository Structure

```
├── PROTOCOL.md          # Full protocol specification
├── README.md            # This file
├── amb                  # CLI client (Python 3.8+)
├── amb_node.py          # TCP daemon (asyncio)
├── amb_listener.py      # Optional background subscriber
├── agents/              # Agent configs (gitignored except example)
│   └── example.yaml     # Example agent config
├── templates/           # Claude Code integration
│   ├── inter-agent.template.md   # Protocol rules template
│   ├── amb-relay.template.md     # Relay loop skill template
│   └── setup.sh                  # Config generator
└── .gitignore
```

## Adding a New Agent

1. Create `agents/<name>.yaml` with name, port, workspace path
2. Run `bash templates/setup.sh`
3. Agent starts with `amb start` — automatically joins the mesh

See [PROTOCOL.md](PROTOCOL.md) for the full specification.

## Requirements

- Python 3.8+
- No external dependencies (stdlib only: asyncio, socket, json)
