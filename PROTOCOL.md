# AMB — Agent Message Bus Protocol v5.0

A peer-to-peer TCP mesh protocol for LLM agent collaboration.

---

## Overview

AMB enables multiple Claude Code (or other LLM) agents to communicate in real-time via a lightweight TCP mesh. Each agent runs a daemon on a unique port. Messages are delivered directly peer-to-peer with <1ms latency.

**Key properties:**
- No central server — fully decentralized mesh
- Persistent message storage (JSONL append-only logs)
- Offline delivery — messages wait in inbox until agent reconnects
- Activity tracking — each agent broadcasts what it's working on
- Sub-second latency for online agents
- Background task tracking — delegating agent monitors completion
- Background AMB listener — agent stays reachable during long tasks
- Mandatory cross-review — every change reviewed by another agent
- Post-incident learning — mistakes feed back into team knowledge

---

## Architecture

```
┌──────────────┐    TCP deliver    ┌──────────────┐
│  amb_node.py  │ ───────────────→ │  amb_node.py  │
│  Agent A      │ ←─── ack ─────── │  Agent B      │
│  :PORT_A      │                  │  :PORT_B      │
└──────────────┘                  └──────────────┘
        ↕ heartbeat (30s)                 ↕
┌──────────────┐                  ┌──────────────┐
│  amb_node.py  │ ←── heartbeat ──→│  amb_node.py  │
│  Agent C      │                  │  Agent D      │
│  :PORT_C      │                  │  :PORT_D      │
└──────────────┘                  └──────────────┘

Shared: peers.json (auto-discovered peer registry)
Per-node: bus/{name}.jsonl (persistent log), bus/{name}.pid
```

---

## Setup

### 1. Define your agent

Create a YAML config in `agents/` directory:

```yaml
# agents/my-agent.yaml
name: MyAgent
port: 15000
workspace: /path/to/workspace
role: developer
report_dir: /path/to/workspace/reports
```

### 2. Run setup

```bash
cd agent_communication_protocol
bash templates/setup.sh    # reads agents/*.yaml, generates configs
```

This creates:
- `{workspace}/.claude/rules/inter-agent.md` — protocol rules for the agent
- `{workspace}/.claude/skills/amb-relay/SKILL.md` — relay loop skill

### 3. Start your node

```bash
export AMB_NAME=MyAgent
export AMB_PORT=15000
amb start              # start TCP daemon
amb recv               # check pending messages
amb activity "listening"
```

### 4. Communicate

```bash
amb send --to AgentB "hello"          # direct message
amb send --to '*' "broadcast"         # broadcast to all
amb recv                              # read pending (one-shot)
amb recv --wait 600                   # subscribe for 10 min
amb unread                            # peek count without consuming
amb status                            # all agents + activity
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `amb start` | Start your mesh node (background daemon) |
| `amb stop` | Stop your node |
| `amb send --to <name> "msg"` | Send message to agent |
| `amb send --to '*' "msg"` | Broadcast to all peers |
| `amb recv` | Read pending messages (one-shot, advances cursor) |
| `amb recv --wait N` | Subscribe for N seconds, return on message or timeout |
| `amb recv --wait N --batch M` | Return after M messages or timeout |
| `amb recv --follow` | Persistent live subscribe |
| `amb unread` | Peek unread count without consuming |
| `amb check` | Read from offline inbox file (no TCP needed) |
| `amb peers` | Show registered peers |
| `amb status` | Full network status: all agents, activity, heartbeat |
| `amb activity "text"` | Update your activity status |
| `amb ping` | Check your node is alive |

---

## Wire Protocol

TCP, line-delimited JSON. Each message is a single JSON object followed by `\n`.

| Operation | Direction | Format |
|-----------|-----------|--------|
| `deliver` | sender → recipient node | `{"op":"deliver","from":"A","id":"uuid8","body":"text","ts":N}` |
| `ack` | recipient → sender | `{"op":"ack","id":"uuid8"}` |
| `read` | agent → own node | `{"op":"read"}` → messages + `{"op":"read_end","count":N}` |
| `subscribe` | agent → own node | `{"op":"subscribe"}` → backlog + live push |
| `peek` | agent → own node | `{"op":"peek"}` → `{"op":"peek_result","unread":N}` |
| `set_activity` | agent → own node | `{"op":"set_activity","text":"working on X"}` |
| `peers` | anyone → any node | `{"op":"peers"}` → peer registry |
| `register` | node → other nodes | `{"op":"register","name":"A","host":"H","port":P}` |
| `ping` | anyone → any node | `{"op":"ping"}` → `{"op":"pong","name":"A","inbox_size":N,...}` |
| `heartbeat_sub` | node → subscriber | `{"op":"heartbeat_sub","ts":N}` (keepalive, ignored by CLI) |

---

## Task Delegation Protocol

Structured format for assigning work between agents:

### Task Assignment (lead → worker)

```
TASK: [imperative verb — "Fix", "Find", "Verify"]
CONTEXT: [why this is needed, what is known]
SCOPE: [what is in / out of scope]
OUTPUT: [file path / table / numbers]
DONE CRITERIA: [specific measurable condition]
PRIORITY: HIGH | MEDIUM | LOW
```

### Task Acknowledgment

Agent MUST evaluate before accepting:
1. Read the task fully
2. Assess — agree with approach? See a better way? Spot problems?
3. If agree: `"Accepted, starting."`
4. If disagree: `"Disagree: [reason]. Propose: [alternative]."` — expected and healthy.

### Task Reports

Write results to files, send only short references via AMB:
```
Done: ~/workspace/reports/task-name.md
```

On error:
```
ERROR: [what happened]
CAUSE: [root cause]
SUGGESTION: [proposed fix]
```

### Background Task Tracker (MANDATORY)

When delegating a task, the lead agent MUST launch a background subagent to track completion. This prevents fire-and-forget delegation where tasks silently die.

**Pattern for Claude Code agents:**

```
After sending the AMB task, immediately call:

Agent tool:
  description: "Track task [short name]"
  run_in_background: true
  prompt: |
    You are a task tracker. Monitor AMB for a response to a delegated task.

    TASK DETAILS:
    - Sent to: [AgentName]
    - Subject: [task description]
    - Deadline: [date]

    MONITORING LOOP:
    1. Run: AMB_NAME=${AMB_NAME} AMB_PORT=${AMB_PORT} amb recv --wait 300 --batch 1
    2. If you receive a message from [AgentName] about this task:
       - Acknowledgment ("Accepted") → note it, continue monitoring for result
       - Result ("Done: [path]") → report to operator:
         "[AgentName] completed: [task]. Result: [path]. Needs cross-review."
       - Question or blocker → report to operator immediately
    3. If 30 minutes pass with no acknowledgment → alert operator
    4. If deadline passes without result → escalate to operator
    5. After receiving result OR escalating → stop.

    Between polls, just wait. Do not do any other work.
```

**Why this matters:** Without a tracker, delegated tasks disappear into the void. The tracker ensures every task gets acknowledged, monitored, and closed.

---

## Background AMB Listener

When an agent starts a long task (>5 minutes), it becomes unreachable via AMB — corrections, priority changes, and new tasks go unnoticed. The solution: launch a background listener before starting work.

**Pattern for Claude Code agents:**

```
Before starting the main work, call:

Agent tool:
  description: "AMB listener"
  run_in_background: true
  prompt: |
    You are an AMB listener running in the background while the main agent works.

    LISTENING LOOP:
    1. Run: AMB_NAME=${AMB_NAME} AMB_PORT=${AMB_PORT} amb recv --wait 300 --batch 1
    2. If you receive a message:
       - Correction/priority change → report to operator IMMEDIATELY
       - New task → report: "New task from [sender]. Main agent busy with [task]."
       - Status request → reply via AMB: "Working on [task]. ETA: [estimate]."
       - Question → answer if possible, otherwise report to operator
    3. Run amb recv again. Repeat until main work completes.

    You are PASSIVE — only listen and relay. Do not start new work.
```

**When to launch:** any implementation task, multi-step analysis, or task >5 minutes.
**When NOT to launch:** quick operations (<2 min), already in relay mode, during short cross-review.

---

## Communication Rules

### Challenge Obligation

Agents MUST challenge decisions they disagree with:
- See a better approach → speak up with evidence
- See a flaw → speak up before execution
- Silent agreement = bad sign
- Resolution: evidence > authority. Only the human operator overrides.

### Artifacts to Filesystem

Do NOT send long content via AMB. Write to files, send references.
Rule of thumb: body > 500 characters → use a file.

### Error Transparency

Agents report errors immediately and clearly. Never hide failures.

---

## File-Based Threads

For formal tasks, specs, and cross-review that need persistent records:

```
threads/T{NNN}-{slug}/
├── 001-{Author}-request.md
├── 002-{Author}-response.md
└── ...
```

| Type | needs_response | Description |
|------|:-:|------|
| `request` | yes | Need answer/decision |
| `response` | no | Answer to request |
| `reject` | no | Argued rejection |
| `info` | no | FYI notification |
| `done` | no | Task completed |
| `review` | yes | Cross-review request |
| `escalation` | yes | Blocker → human operator |

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `AMB_NAME` | yes | Agent name (used in messages and peer registry) |
| `AMB_PORT` | yes | TCP port for this agent's daemon |
| `AMB_HOST` | no | Bind address (default: `127.0.0.1`) |
| `AMB_BUS_DIR` | no | Directory for runtime files (default: `./bus/`) |
| `AMB_PEERS` | no | Path to peers.json (default: `./peers.json`) |

### peers.json

Auto-updated peer registry. Agents register on startup.

```json
{
  "AgentA": {"host": "127.0.0.1", "port": 15000},
  "AgentB": {"host": "127.0.0.1", "port": 15001}
}
```

### Agent Config (agents/*.yaml)

```yaml
name: AgentName          # AMB_NAME
port: 15000              # AMB_PORT
workspace: /path/to/ws   # where .claude/ configs are generated
role: developer           # for documentation
report_dir: reports/      # relative to workspace
```

---

## Technical Details

- **Reconnect safety:** Node stores cursor per-subscriber. On reconnect, backlog is replayed from last cursor position.
- **TCP keepalive:** `SO_KEEPALIVE` with `KEEPIDLE=30s`, `KEEPINTVL=10s`, `KEEPCNT=3` — detects dead connections in ~60s.
- **Subscriber heartbeat:** Node sends `heartbeat_sub` every 60s to detect zombie subscribers.
- **Cursor advance:** Read cursor advances on every successful push, preventing duplicates on re-subscribe.
- **Offline inbox:** Node writes `_inbox.jsonl` on every deliver. `amb check` reads it without TCP.
- **Recommended poll interval:** 600s (10 min) for relay loops. Reduces reconnect churn while staying responsive.

---

## Cross-Review Protocol

Every significant change must be reviewed by another agent before acceptance. This is not optional — unreviewed changes are rejected.

### Review Matrix

| Change type | Author | Reviewer | What to check |
|-------------|--------|----------|---------------|
| Code (C++, configs) | Dev agent | Research agent | Correctness, safety, spec compliance, root cause |
| Research (audits, specs) | Research agent | Dev agent | Implementability, edge cases, hardware realism |
| Architecture decisions | Architect | Both agents | Evidence basis, alternatives, feasibility |
| Agent configs | Coach | Affected agent | No workflow breakage, budget compliance |

### Review Process

1. Author completes work → sends AMB: "Готово: [path]. Прошу кросс-ревью."
2. Reviewer reads the deliverable
3. Reviewer sends feedback via AMB (short) or file (detailed):
   - `APPROVE: [what was verified, caveats if any]`
   - `NEEDS CHANGES: [specific issues with file:line references]`
   - `REJECT: [fundamental problems, alternative approach suggested]`
4. Author addresses feedback or argues with evidence
5. After approval → task can be closed

### Dispute Resolution

Disagreement between agents is **healthy and expected**. Resolution protocol:

1. Both sides state their position with **evidence** (measurements, source code, calculations)
2. If unresolved after 2 rounds → escalate to human operator with both positions documented
3. Only the human operator overrides an agent's reasoned objection
4. Every resolution must be documented (AMB thread or file)

**Red flag:** If an agent accepts everything without pushback — something is wrong. Challenge silence.

---

## Team Learning Protocol

Agents must learn from mistakes — their own and each other's.

### Post-Incident

After any bug, crash, failed approach, or rejected deliverable:

1. **Root cause analysis** — not "what broke" but "why the system allowed it to break"
   - Use 5 Whys: symptom → cause → cause → ... → architectural root
   - A `clamp()` or `if (bad) return` is NEVER a root cause fix
2. **Capture the lesson** — write it down where it prevents recurrence:
   - Code bug → add to knowledge base or rule
   - Process failure → add to agent rules
   - Research gap → update methodology skill
3. **Notify other agents** — if the lesson applies beyond the agent who found it:
   - AMB: `"LESSON: [what] / SOURCE: [incident] / APPLIES TO: [agents]"`
4. **Verify prevention** — can the fix be tested? automated? caught in review?

### Pattern Detection

If the same class of problem occurs 3+ times → it's systemic:
- Not a bug to fix, but a process to redesign
- Escalate to architect or coach for structural solution
- Add a hook, rule, or quality gate to prevent the entire class
