# Inter-Agent Protocol

Source of truth: PROTOCOL.md in the agent_communication_protocol repository.

## AMB Bootstrap (MANDATORY at session start)

```bash
export AMB_NAME={AGENT_NAME}
export AMB_PORT={AGENT_PORT}
amb start
amb recv
amb activity "listening"
```

## Communication Rules

1. **Challenge obligation:** If you disagree with an approach — SAY SO with arguments. Silence ≠ agreement. Disagreement with evidence = healthy.
2. **Reports go to files**, AMB gets only short refs. Do NOT send long texts via AMB.
3. **Acknowledge tasks:** "Accepted, starting." OR "Disagree: [reason]. Propose: [alternative]."
4. **Report errors clearly:** "ERROR: [what] / CAUSE: [why] / SUGGESTION: [fix]"

## Task Format

```
TASK: [imperative verb]
CONTEXT: [why, what's known]
SCOPE: [in / out of scope]
OUTPUT: [file path / format]
DONE CRITERIA: [done condition]
PRIORITY: HIGH | MEDIUM | LOW
```
