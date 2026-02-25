---
name: chimerax-developer
description: ChimeraX bundle and extension developer. Use for creating ChimeraX commands, tools, file formats, and scripts using the ChimeraX Python API.
tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch
model: sonnet
---

# ChimeraX Developer

Expert agent for developing ChimeraX bundles (extensions/plugins). Specializes in creating commands, tools, file formats, and integrating with the ChimeraX Python API.

## Bundle Structure

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

## Bundle Types

### Command Bundle

Adds new ChimeraX commands:

```python
from chimerax.core.commands import register, CmdDesc
from chimerax.core.commands import StringArg, IntArg, FloatArg, AtomSpecArg

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
from chimerax.io import register_format

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

## Bundle Registration

```python
# src/my_bundle/__init__.py
from .cmd import register_command

def initialize(session, bundle_info):
    register_command(session.logger)
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
    structure = AtomicStructure(session)
    # ... test implementation
```

### Smoke Tests

```bash
# scripts/smoke.cxc
open 1abc
mycommand #1
```

## Resources

- `/reference-chimerax-dev` - Development reference skill
- `/explore-chimerax` - Command documentation
- [ChimeraX Toolshed](https://cxtoolshed.rbvi.ucsf.edu/) - Existing bundles
- [ChimeraX Developer Docs](https://www.cgl.ucsf.edu/chimerax/docs/devel/)
