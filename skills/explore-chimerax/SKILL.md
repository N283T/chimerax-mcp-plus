---
name: explore-chimerax
description: ChimeraX command exploration and documentation reference
allowed-tools: Read, Glob, Grep, Bash
timeout: 120000
---

# ChimeraX Commands & Documentation

Reference for ChimeraX commands, documentation lookup, and MCP operation.

For bundle/extension development, use `/reference-chimerax-dev`.

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

## Index & Docs Paths

```bash
DOC_INDEX="${SKILL_ROOT}/assets/chimerax-1.9.index.json"
DOC_ROOT="${SKILL_ROOT}/assets/docs"
```

## Primary Workflow: Index-Based Lookup

### 1. Find the command

```bash
# Exact command lookup
jq '.commands["color"]' "$DOC_INDEX"

# Search by partial name
jq -r '.commands | to_entries[] | select(.key | test("surf")) | .key' "$DOC_INDEX"

# Search by keyword (returns doc paths)
jq '.keywords["distance"]' "$DOC_INDEX"

# List all command names
jq -r '.commands | keys[]' "$DOC_INDEX"
```

### 2. Read full documentation

Once you have the command name, read its HTML doc:

```bash
# Get the relative path
jq -r '.commands["color"].path' "$DOC_INDEX"
# -> user/commands/color.html

# Read the full doc
Read ${SKILL_ROOT}/assets/docs/user/commands/color.html
```

### 3. Extract command syntax

From the docs, extract:
- Command name and aliases
- Required arguments
- Optional arguments
- Atom specification syntax
- Examples

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

## Error Resolution Flow

When a ChimeraX command fails:

### Step 1: Get built-in help

```
chimerax_run("help <command>")
```

### Step 2: Search the index

```bash
# Find the command in the index
jq '.commands["<command>"]' "$DOC_INDEX"

# Search by keyword if command name is unclear
jq '.keywords | to_entries[] | select(.key | test("<keyword>")) | {key: .key, paths: .value}' "$DOC_INDEX"
```

### Step 3: Read the documentation

```
Read ${SKILL_ROOT}/assets/docs/<path-from-index>
```

### Step 4: Find related commands

```bash
# Related commands often share keywords
jq '.keywords["<keyword>"]' "$DOC_INDEX"
```

## Comprehensive Exploration Flow

When exploring what ChimeraX can do:

### By category

```bash
# All commands with their titles
jq -r '.commands | to_entries[] | "\(.key): \(.value.title)"' "$DOC_INDEX"

# Filter by keyword category
jq -r '.keywords["surface"][]' "$DOC_INDEX"
jq -r '.keywords["align"][]' "$DOC_INDEX"
jq -r '.keywords["color"][]' "$DOC_INDEX"
```

### By functionality

| Goal | Keywords to search |
|------|--------------------|
| Structure loading | `open`, `fetch`, `load` |
| Visualization | `color`, `surface`, `cartoon`, `style` |
| Analysis | `measure`, `distance`, `angle`, `clash` |
| Selection | `select`, `zone`, `name` |
| Export | `save`, `export`, `image` |
| Alignment | `align`, `match`, `superpose` |
| Maps/Density | `volume`, `density`, `contour` |

## Command Categories

### Structure Loading

| Command | Description |
|---------|-------------|
| `open` | Open file or fetch from database |
| `close` | Close models |
| `save` | Save structures/images |

### Visualization

| Command | Description |
|---------|-------------|
| `color` | Color atoms, surfaces, etc. |
| `style` | Set atom/bond style |
| `cartoon` | Cartoon representation |
| `surface` | Generate molecular surface |
| `hide` / `show` | Hide/show atoms |
| `transparency` | Set transparency |

### Selection & Specification

| Command | Description |
|---------|-------------|
| `select` | Select atoms |
| `name` | Name selections |
| Atom spec | `#1/A:10-20@CA` syntax |

### Analysis

| Command | Description |
|---------|-------------|
| `measure` | Distances, angles, etc. |
| `clashes` | Find clashes/contacts |
| `hbonds` | Find hydrogen bonds |
| `contacts` | Find contacts |
| `align` | Align structures |

### Camera & View

| Command | Description |
|---------|-------------|
| `view` | Set view |
| `camera` | Camera settings |
| `clip` | Clipping planes |
| `lighting` | Lighting settings |

## Atom Specification Syntax

ChimeraX uses hierarchical atom specification:

```
#model/chain:residue@atom
```

Examples:
- `#1` - Model 1
- `#1/A` - Chain A of model 1
- `#1/A:10-20` - Residues 10-20 of chain A
- `#1/A:10@CA` - CA atom of residue 10
- `protein` - All protein atoms
- `ligand` - All ligand atoms
- `solvent` - All solvent atoms

Reference: `${SKILL_ROOT}/assets/docs/user/commands/atomspec.html`

## MCP Operation Guide

When operating ChimeraX via MCP:

### Format commands correctly

Commands should be valid ChimeraX command-line syntax:
```
open 1abc
color protein cornflowerblue
surface protein
```

### Chain commands

Multiple commands can be separated by `;`:
```
open 1abc; color protein gold; surface
```

### Handle errors

Check command output for errors. Common issues:
- Invalid atom specification -> check atomspec syntax above
- Unknown command -> search index for correct name
- Missing model -> verify model number with `models` tool

## Common Tasks

### Open and visualize a PDB

```
open 1abc
color protein bychain
cartoon
surface protein transparency 0.5
```

### Highlight binding site

```
select :LIG
select zone :LIG 5 protein
color sel red
surface sel
```

### Measure distance

```
measure distance #1/A:10@CA #1/A:20@CA
```

### Save image

```
save image.png width 1920 height 1080 supersample 4
```

## Usage

```
/explore-chimerax                      # Interactive - describe what you want
/explore-chimerax color protein        # Find coloring commands
/explore-chimerax measure distance     # Find measurement commands
/explore-chimerax open pdb             # File loading
```
