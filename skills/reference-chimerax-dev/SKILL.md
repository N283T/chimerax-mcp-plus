---
name: reference-chimerax-dev
description: ChimeraX bundle/extension development reference
allowed-tools: Read, Glob, Grep, WebSearch, WebFetch, Bash
timeout: 120000
---

# ChimeraX Bundle Development

Reference for developing ChimeraX bundles (extensions/plugins).

## Query Index

Use the pre-built index for fast documentation lookup:

```bash
DOC_INDEX="${HOME}/.claude/skills/explore-chimerax/assets/chimerax-1.9.index.json"

# List all tutorials
jq '.tutorials | keys[]' "$DOC_INDEX"

# Find tutorial by name
jq '.tutorials["tutorial_command"]' "$DOC_INDEX"

# List API modules
jq '.modules | keys[]' "$DOC_INDEX"

# Find module by name
jq '.modules["atomic"]' "$DOC_INDEX"

# Search by keyword
jq '.keywords["bundle"]' "$DOC_INDEX"
```

## Reference Priority

**Always check in this order:**

| Priority | Source | Location |
|----------|--------|----------|
| 1 | Local devel docs | `${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/` |
| 2 | ChimeraX Toolshed | https://cxtoolshed.rbvi.ucsf.edu/ |
| 3 | GitHub examples | Search `chimerax bundle` or `chimerax extension` |

## Documentation Reference

Local docs at `${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/`

### Key Documentation Files

| File | Description |
|------|-------------|
| `writing_bundles.html` | Complete bundle development guide |
| `tutorials/introduction.html` | Getting started |
| `tutorials/tutorial_hello.html` | Hello World bundle |
| `tutorials/tutorial_command.html` | Creating commands |
| `tutorials/tutorial_tool.html` | Creating tools (panels) |
| `bundles.html` | Bundle structure and metadata |
| `core.html` | Core API overview |

### API Modules

Located at `modules/`:

| Module | Description |
|--------|-------------|
| `atomic/` | Atomic structure manipulation |
| `core/` | Core functionality |
| `geometry/` | Geometric operations |
| `graphics/` | 3D graphics |
| `io/` | File I/O |
| `map/` | Density maps |
| `surface/` | Surface generation |
| `ui/` | User interface |

## Bundle Types

What type of bundle?
- **Command**: Adds new ChimeraX command
- **Tool**: Adds GUI panel/dialog
- **File format**: Reads/writes new format
- **Preset**: Adds visualization presets

## Find Relevant Tutorial

```
Read ${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/tutorials/introduction.html
```

Tutorials by type:
- Command: `tutorial_command.html`
- Tool (Qt): `tutorial_tool_qt.html`
- Tool (HTML): `tutorial_tool_html.html`
- File format read: `tutorial_read_format.html`
- File format save: `tutorial_save_format.html`
- Fetch: `tutorial_fetch.html`
- Presets: `tutorial_presets.html`
- Selector: `tutorial_selector.html`

## Reference API Documentation

```
Glob ${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/modules/**/*.html
Read ${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/modules/atomic/index.html
```

## Project Structure

```
bundle_name/
├── pyproject.toml      # Bundle metadata
├── src/
│   └── __init__.py     # Bundle initialization
│   └── cmd.py          # Commands
├── tests/              # Test files
├── scripts/
│   └── smoke.cxc       # Test script
└── README.md
```

## Reference pyproject.toml Format

```
Read ${HOME}/.claude/skills/explore-chimerax/assets/docs/devel/tutorials/pyproject.html
```

## Common Patterns

### Register a command

```python
from chimerax.core.commands import register, CmdDesc
from chimerax.core.commands import StringArg, IntArg

def my_command(session, name, count=1):
    session.logger.info(f"Hello {name} x{count}")

my_command_desc = CmdDesc(
    required=[("name", StringArg)],
    optional=[("count", IntArg)],
    synopsis="Say hello"
)

def register_command(logger):
    register("mycommand", my_command_desc, my_command, logger=logger)
```

### Create a tool

```python
from chimerax.core.tools import ToolInstance

class MyTool(ToolInstance):
    SESSION_ENDURING = False
    SESSION_SAVE = True

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)
        # Build UI
```

## Finding Third-Party Bundles

When local docs aren't enough, search for existing bundles as references.

### ChimeraX Toolshed

Official bundle repository:
```
WebFetch https://cxtoolshed.rbvi.ucsf.edu/
"List available ChimeraX bundles and their descriptions"
```

### GitHub Search

Search for similar bundles:
```
WebSearch "chimerax bundle [feature] site:github.com"
WebSearch "chimerax extension [feature] site:github.com"
```

Example searches:
- `chimerax bundle symmetry site:github.com`
- `chimerax extension density map site:github.com`
- `chimerax tool panel site:github.com`

### Useful Repositories

| Repository | Description |
|------------|-------------|
| RBVI/ChimeraX | Official ChimeraX (includes core bundles) |
| cxtoolshed repos | Community bundles |

### Learning from Existing Bundles

1. Find a bundle with similar functionality
2. Clone or browse its source
3. Study the structure:
   - `pyproject.toml` - metadata and dependencies
   - `src/*/cmd.py` - command registration
   - `src/*/tool.py` - UI implementation
4. Adapt patterns to your needs

## Usage

```
/reference-chimerax-dev                     # Interactive guidance
/reference-chimerax-dev command tutorial    # Command development
/reference-chimerax-dev tool panel          # Tool/panel development
/reference-chimerax-dev atomic API          # Atomic module reference
/reference-chimerax-dev find symmetry       # Search for symmetry-related bundles
```
