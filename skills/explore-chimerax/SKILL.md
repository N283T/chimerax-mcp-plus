---
name: explore-chimerax
description: ChimeraX documentation reference (router to sub-skills)
allowed-tools: Read, Glob, Grep
timeout: 60000
---

# ChimeraX

UCSF ChimeraX documentation reference skill.

## Sub-Skills

| Skill | Use For |
|-------|---------|
| `/reference-chimerax-dev` | Bundle/extension development |
| `/explore-chimerax-commands` | Command exploration, MCP operation |

## Documentation Location

Local ChimeraX docs are at:
```
${SKILL_ROOT}/assets/docs/
```

**Structure:**
- `docs/devel/` - Developer documentation (API, bundle development)
- `docs/user/` - User documentation (commands, formats)

## Pre-built Index

A JSON index is committed at:
```
${SKILL_ROOT}/assets/chimerax-1.9.index.json
```

Current version: **1.9** (149 commands, 13 tutorials, 16 modules)

### Rebuild Index (version update only)

```bash
uv run ${SKILL_ROOT}/build_doc_index.py \
  ${SKILL_ROOT}/assets/docs \
  <VERSION> \
  ${SKILL_ROOT}/assets/chimerax-<VERSION>.index.json
```

## Query Index

```bash
DOC_INDEX="${SKILL_ROOT}/assets/chimerax-1.9.index.json"
```

### Find commands

```bash
# List all command names
jq -r '.commands | keys[]' "$DOC_INDEX"

# Get command info (path, title, description)
jq '.commands["color"]' "$DOC_INDEX"

# Search commands by partial name
jq '.commands | to_entries[] | select(.key | test("surf"))' "$DOC_INDEX"

# Get command doc path for reading
jq -r '.commands["color"].path' "$DOC_INDEX"
# → user/commands/color.html
# Read: ${SKILL_ROOT}/assets/docs/user/commands/color.html
```

### Find tutorials

```bash
jq -r '.tutorials | keys[]' "$DOC_INDEX"
jq '.tutorials["tutorial_command"]' "$DOC_INDEX"
```

### Find API modules

```bash
jq -r '.modules | keys[]' "$DOC_INDEX"
jq '.modules["atomic"]' "$DOC_INDEX"
```

### Search by keyword

```bash
# Find all docs mentioning "surface"
jq '.keywords["surface"]' "$DOC_INDEX"

# Search keywords by partial match
jq '.keywords | to_entries[] | select(.key | test("dist"))' "$DOC_INDEX"
```

## Routing

Based on user request, route to appropriate sub-skill:

| Request Pattern | Route To |
|-----------------|----------|
| "create bundle", "write extension", "develop plugin" | `/reference-chimerax-dev` |
| "what command", "how to", "MCP", "operate" | `/explore-chimerax-commands` |
