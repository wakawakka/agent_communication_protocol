# Example: Hierarchical Team (CTO + Engineers)

A 3-agent team with a lead architect who delegates tasks to two specialist engineers.

## Team Structure

```
Operator (human)
    └── Lead (CTO / Architect)        — port 15000
            ├── Engineer (Dev+QA)      — port 15001
            └── Analyst (R&D)          — port 15002
```

## Setup

```bash
cd agent_communication_protocol

# 1. Create agent configs
cp examples/hierarchy-team/agents/*.yaml agents/

# 2. Generate Claude Code configs
bash templates/setup.sh

# 3. Start nodes (each agent in its own terminal)
# Terminal 1 (Lead):
AMB_NAME=Lead AMB_PORT=15000 amb start

# Terminal 2 (Engineer):
AMB_NAME=Engineer AMB_PORT=15001 amb start

# Terminal 3 (Analyst):
AMB_NAME=Analyst AMB_PORT=15002 amb start

# 4. Verify mesh
AMB_NAME=Lead AMB_PORT=15000 amb status
```

## Communication Patterns

### Lead delegates a task
```bash
AMB_NAME=Lead AMB_PORT=15000 amb send --to Engineer \
  "TASK: Fix the login timeout bug
CONTEXT: Users report 504 errors after 30s. Server logs show DB query takes 45s.
SCOPE: Backend only. Do not touch frontend.
OUTPUT: ~/engineer-workspace/reports/login-timeout-fix.md
DONE CRITERIA: Login completes in <5s, no 504 errors in 100 requests
PRIORITY: HIGH"
```

### Engineer reports back
```bash
AMB_NAME=Engineer AMB_PORT=15001 amb send --to Lead \
  "Done: ~/engineer-workspace/reports/login-timeout-fix.md
Root cause: missing index on users.last_login. Added index, p95 latency 200ms→50ms."
```

### Lead asks Analyst to review
```bash
AMB_NAME=Lead AMB_PORT=15000 amb send --to Analyst \
  "TASK: Review Engineer's fix for login timeout
CONTEXT: Engineer added DB index. Fix in ~/engineer-workspace/reports/login-timeout-fix.md
SCOPE: Check correctness, performance impact, migration safety
OUTPUT: AMB verdict — APPROVE or REJECT with reasons
DONE CRITERIA: Review complete
PRIORITY: HIGH"
```

### Analyst challenges the approach
```bash
AMB_NAME=Analyst AMB_PORT=15002 amb send --to Lead \
  "Disagree: Adding index fixes symptom, not cause.
The query joins 3 tables without WHERE clause filtering — index helps but query
will degrade again at 10x data. Propose: rewrite query with proper filtering + index.
Evidence: EXPLAIN ANALYZE shows seq scan on orders table (2M rows)."
```

## Key Principles

1. **Lead delegates, doesn't execute** — designs architecture, reviews deliverables
2. **Engineer implements and tests** — writes code, runs tests, reports results
3. **Analyst researches and reviews** — finds root causes, reviews approaches
4. **Challenge obligation** — agents must disagree when they see a better way
5. **Artifacts to files** — long reports go to files, AMB gets short references
6. **Task watcher** — Lead launches background subagent to monitor task completion
