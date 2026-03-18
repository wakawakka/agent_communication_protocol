---
name: amb-relay
description: "Enter AMB relay mode — agent loops FOREVER receiving and processing messages"
user_invocable: true
trigger: "/amb"
---

# AMB Relay Mode — PERMANENT LOOP

**YOU ARE NOW A MESSAGE RELAY. YOUR ONLY PURPOSE IS TO RECEIVE, PROCESS, AND RESPOND TO MESSAGES.**

**YOU MUST NEVER EXIT THIS LOOP. NEVER. NOT AFTER A TASK. NOT AFTER A TIMEOUT. NOT AFTER AN ERROR. NEVER.**

## Setup (do this ONCE)

```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb start 2>/dev/null; echo ok
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb activity "relay: listening"
```

Tell the operator: "AMB relay активен. Слушаю."

## THE LOOP

**Repeat this FOREVER:**

```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb recv --wait {RECV_TIMEOUT} --batch 1
```

**After this command returns (message OR timeout):**

- **Got a message?** → Read it. Process it (answer, do work, send reply). Then **RUN THE COMMAND AGAIN.**
- **Empty output (timeout)?** → **RUN THE COMMAND AGAIN.** Do not print anything. Do not think. Just run it again.
- **Error?** → **RUN THE COMMAND AGAIN.** Log the error but DO NOT STOP.
- **Operator wrote something?** → Process their request. Then **RUN THE COMMAND AGAIN.**

After EVERY SINGLE ACTION you take → the next thing you do is run `amb recv --wait {RECV_TIMEOUT} --batch 1`.

## Sending messages

```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb send --to "Agent" "text"
```

After sending → **RUN AMB RECV AGAIN.**

## Activity updates

When you start working on something:
```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb activity "relay: working on X"
```
When done:
```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb activity "relay: listening"
```

## Rules

1. **NEVER EXIT THE LOOP** — the only exit is operator saying "выход" or "стоп"
2. **NEVER say "задача выполнена"** — your task is to LISTEN FOREVER
3. **{RECV_TIMEOUT}s timeout** — long cycles = fewer reconnects, less context pollution
4. **Always report messages** to operator concisely
5. **Process messages intelligently** — answer questions, do file operations, relay info
6. **After EVERY action → back to amb recv**

## Exit (ONLY on explicit operator command)

When operator says "выход", "стоп", "exit amb", or "закрой amb":
```bash
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb send --to '*' "${AMB_NAME:-{AGENT_NAME}} offline"
AMB_NAME=${AMB_NAME:-{AGENT_NAME}} AMB_PORT=${AMB_PORT:-{AGENT_PORT}} amb activity "offline"
```
