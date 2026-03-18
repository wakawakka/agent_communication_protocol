#!/bin/bash
# setup.sh — Generate agent-specific configs from templates + agent YAML files.
#
# Usage:
#   bash setup.sh                    # process all agents/*.yaml
#   bash setup.sh agents/alice.yaml  # process specific agent
#
# For each agent config, generates:
#   {workspace}/.claude/rules/inter-agent.md
#   {workspace}/.claude/skills/amb-relay/SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
AGENTS_DIR="$REPO_DIR/agents"
TEMPLATE_RULES="$SCRIPT_DIR/inter-agent.template.md"
TEMPLATE_SKILL="$SCRIPT_DIR/amb-relay.template.md"

# Parse YAML value (simple key: value, no nested)
yaml_val() {
    grep "^${2}:" "$1" 2>/dev/null | sed "s/^${2}:[[:space:]]*//" | sed 's/[[:space:]]*#.*//' | tr -d '"' | tr -d "'"
}

process_agent() {
    local config="$1"
    local name port workspace role report_dir

    name="$(yaml_val "$config" name)"
    port="$(yaml_val "$config" port)"
    workspace="$(yaml_val "$config" workspace)"
    role="$(yaml_val "$config" role)"
    report_dir="$(yaml_val "$config" report_dir)"

    if [ -z "$name" ] || [ -z "$port" ] || [ -z "$workspace" ]; then
        echo "  SKIP: $config (missing name, port, or workspace)"
        return 1
    fi

    echo "  Generating configs for $name (port $port, workspace $workspace)..."

    # inter-agent.md
    mkdir -p "$workspace/.claude/rules"
    sed -e "s|{AGENT_NAME}|$name|g" \
        -e "s|{AGENT_PORT}|$port|g" \
        "$TEMPLATE_RULES" > "$workspace/.claude/rules/inter-agent.md"

    # amb-relay SKILL.md
    mkdir -p "$workspace/.claude/skills/amb-relay"
    sed -e "s|{AGENT_NAME}|$name|g" \
        -e "s|{AGENT_PORT}|$port|g" \
        "$TEMPLATE_SKILL" > "$workspace/.claude/skills/amb-relay/SKILL.md"

    # Create report directory
    if [ -n "$report_dir" ]; then
        mkdir -p "$workspace/$report_dir"
    fi

    echo "  Done: $name"
}

echo "AMB Agent Config Generator"
echo "=========================="

if [ $# -gt 0 ]; then
    # Process specific files
    for f in "$@"; do
        process_agent "$f"
    done
else
    # Process all agents/*.yaml (except example)
    count=0
    for config in "$AGENTS_DIR"/*.yaml; do
        [ "$(basename "$config")" = "example.yaml" ] && continue
        [ -f "$config" ] || continue
        process_agent "$config"
        count=$((count + 1))
    done
    if [ "$count" -eq 0 ]; then
        echo "  No agent configs found in $AGENTS_DIR/"
        echo "  Copy agents/example.yaml → agents/your-agent.yaml and edit it."
        exit 1
    fi
    echo ""
    echo "All $count agents configured."
fi
