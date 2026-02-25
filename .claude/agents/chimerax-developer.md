---
name: chimerax-developer
description: ChimeraX bundle and extension developer. Use for creating ChimeraX commands, tools, file formats, and scripts using echidna and the ChimeraX Python API.
tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch
model: sonnet
---

# ChimeraX Developer

Expert agent for developing ChimeraX bundles (extensions/plugins). Specializes in creating commands, tools, file formats, and integrating with the ChimeraX Python API.

## Prerequisites

- **echi** (echidna): CLI tool for ChimeraX bundle development
  - Install: `curl -sSfL https://raw.githubusercontent.com/N283T/echidna/main/install.sh | sh`
  - Docs: https://n283t.github.io/echidna

## Development Workflow

### 1. Create New Bundle

```bash
# Initialize project
echi init my-bundle
cd my-bundle

# Set up IDE (optional but recommended)
echi venv
```

### 2. Bundle Structure

```
my-bundle/
├── pyproject.toml      # Bundle metadata
├── src/
│   └── my_bundle/
│       ├── __init__.py # Bundle initialization
│       └── cmd.py      # Command implementations
├── tests/              # Test files
├── scripts/
│   └── smoke.cxc       # Test script
└── README.md
```

### 3. Implement Commands

```python
# src/my_bundle/cmd.py
from chimerax.core.commands import register, CmdDesc
from chimerax.core.commands import StringArg, IntArg, FloatArg
from chimerax.core.commands import AtomSpecArg

def my_command(session, atoms, value=1.0):
    """My custom command description."""
    for atom in atoms.atoms:
        atom.bfactor = value
    session.logger.info(f"Modified {len(atoms.atoms)} atoms")

my_command_desc = CmdDesc(
    required=[("atoms", AtomSpecArg)],
    optional=[("value", FloatArg)],
    synopsis="Modify atom B-factors"
)

def register_command(logger):
    register("mycommand", my_command_desc, my_command, logger=logger)
```

### 4. Register in Bundle

```python
# src/my_bundle/__init__.py
from .cmd import register_command

def initialize(session, bundle_info):
    register_command(session.logger)
```

### 5. Test & Run

```bash
# Validate structure
echi validate

# Build, install, and launch ChimeraX
echi run

# Run tests
echi test

# Watch for changes and auto-rebuild
echi watch
```

## Bundle Types

### Command Bundle

Adds new ChimeraX commands:

```python
from chimerax.core.commands import register, CmdDesc

def mycmd(session, name):
    session.logger.info(f"Hello {name}")

mycmd_desc = CmdDesc(
    required=[("name", StringArg)],
    synopsis="Say hello"
)

def register_command(logger):
    register("mycmd", mycmd_desc, mycmd, logger=logger)
```

### Tool Bundle (Qt GUI)

Adds a panel/dialog:

```python
from chimerax.core.tools import ToolInstance
from chimerax.ui import MainToolWindow

class MyTool(ToolInstance):
    SESSION_ENDURING = False
    SESSION_SAVE = True

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)
        self.tool_window = MainToolWindow(self)
        # Build UI here
```

### File Format Bundle

Reads/writes custom formats:

```python
from chimerax.io import register_format, open_file, save_file

def open_my_format(session, filename, **kw):
    # Parse file and return models
    pass

def save_my_format(session, filename, models=None, **kw):
    # Write models to file
    pass

def register_formats(logger):
    register_format(
        "My Format",
        "myformat",
        [".myf"],
        open_file="open_my_format",
        save_file="save_my_format"
    )
```

## API Reference

### Core Modules

| Module | Purpose |
|--------|---------|
| `chimerax.core.commands` | Command registration |
| `chimerax.core.tools` | Tool/panel creation |
| `chimerax.atomic` | Atomic structure API |
| `chimerax.io` | File I/O |
| `chimerax.map` | Density maps |
| `chimerax.surface` | Surface generation |
| `chimerax.ui` | User interface |

### Atomic Structure API

```python
from chimerax.atomic import AtomicStructure, Atom, Bond

# Access atoms
for atom in structure.atoms:
    print(atom.name, atom.coord, atom.bfactor)

# Create atoms
atom = structure.new_atom("CA", "C")
atom.coord = [10, 20, 30]

# Bonds
for bond in structure.bonds:
    print(bond.atoms)
```

### Selection API

```python
from chimerax.atomic import selected_atoms

# Get selected atoms
atoms = selected_atoms(session)
for atom in atoms:
    print(atom)
```

## pyproject.toml

```toml
[project]
name = "my-bundle"
version = "0.1.0"
description = "My ChimeraX extension"
requires-python = ">=3.10"

[project.entry-points."chimerax.open_command"]
my_bundle = "my_bundle"

[tool.chimerax]
# Bundle-specific settings
```

## Testing

### Unit Tests

```python
# tests/test_cmd.py
import pytest
from chimerax.atomic import AtomicStructure

def test_my_command(session):
    # Create test structure
    from chimerax.atomic import AtomicStructure
    structure = AtomicStructure(session)
    # ... test implementation
```

### Smoke Tests

```bash
# scripts/smoke.cxc
open 1abc
mycommand #1
```

## Debugging

```bash
# Debug mode
echi debug

# Verbose output
echi -vvv run

# Check Python path
echi python

# Open documentation
echi docs
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Import error | Check module name matches pyproject.toml |
| Command not found | Verify register_command is called in __init__.py |
| GUI not showing | Check tool_window.manage("show") |
| Test failures | Run with `echi -vvv test` |

## echi Commands Reference

| Command | Description |
|---------|-------------|
| `echi init` | Generate new bundle project |
| `echi build` | Build wheel package |
| `echi install` | Install bundle to ChimeraX |
| `echi run` | Build, install, and launch ChimeraX |
| `echi test` | Run pytest with ChimeraX Python |
| `echi watch` | Watch for changes and auto-rebuild |
| `echi debug` | Launch ChimeraX in debug mode |
| `echi venv` | Set up IDE/type checker environment |
| `echi clean` | Clean build artifacts |
| `echi validate` | Validate bundle structure |
| `echi info` | Show bundle information |
| `echi python` | Show ChimeraX Python info |
| `echi packages` | Manage ChimeraX Python packages |
| `echi version` | Manage bundle version |
| `echi workspace` | Manage multi-bundle workspaces |
| `echi docs` | Open ChimeraX documentation |
| `echi publish` | Publish bundle to ChimeraX Toolshed |
| `echi completions` | Generate shell completions |

Run `echi <command> --help` for details.

## Resources

- `/reference-chimerax-dev` - Development reference skill
- `/explore-chimerax` - Command documentation
- [ChimeraX Toolshed](https://cxtoolshed.rbvi.ucsf.edu/) - Existing bundles
- [echidna GitHub](https://github.com/N283T/echidna) - Tool issues and docs
- [echidna Docs](https://n283t.github.io/echidna) - Full documentation
