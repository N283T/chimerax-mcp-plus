# chimerax-mcp

MCP server for controlling UCSF ChimeraX molecular visualization.

## Features

- **ChimeraX Control**: Start, detect, and control ChimeraX via REST API
- **Command Execution**: Run any ChimeraX command
- **Screenshot Capture**: Take screenshots of the current view
- **Session Management**: Save and load ChimeraX sessions
- **echidna Integration**: Build, install, and test ChimeraX bundles

## Installation

```bash
# From source
git clone https://github.com/N283T/chimerax-mcp.git
cd chimerax-mcp
uv pip install -e .
```

## Configuration

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "chimerax": {
      "command": "uv",
      "args": ["run", "chimerax-mcp"],
      "cwd": "/path/to/chimerax-mcp"
    }
  }
}
```

Or if installed globally:

```json
{
  "mcpServers": {
    "chimerax": {
      "command": "chimerax-mcp"
    }
  }
}
```

## Available Tools

### ChimeraX Control

| Tool | Description |
|------|-------------|
| `chimerax_detect` | Detect ChimeraX installation |
| `chimerax_start` | Start ChimeraX with REST API enabled |
| `chimerax_stop` | Stop the ChimeraX process |
| `chimerax_status` | Check if ChimeraX is running |
| `chimerax_run` | Execute any ChimeraX command |
| `chimerax_models` | List open models |
| `chimerax_screenshot` | Capture screenshot (supports auto-fit) |
| `chimerax_tool_screenshot` | Capture screenshot of a tool window |

### View Management

| Tool | Description |
|------|-------------|
| `chimerax_view` | Fit all models or focus on a target |
| `chimerax_turn` | Rotate the view around an axis |
| `chimerax_reset` | Reset display to clean default state |

### Structure Management

| Tool | Description |
|------|-------------|
| `chimerax_open` | Open structure file or fetch from PDB |
| `chimerax_close` | Close models |
| `chimerax_session_save` | Save session |
| `chimerax_session_open` | Load session |

### Bundle Development (echidna)

| Tool | Description |
|------|-------------|
| `bundle_install` | Build and install a bundle |
| `bundle_run` | Build, install, and launch ChimeraX |
| `bundle_test` | Run tests for a bundle |

## Usage Examples

### Basic Workflow

```
User: "Start ChimeraX and open structure 1a0s"

Claude uses chimerax_start → chimerax_open("1a0s")
```

### Taking Screenshots

```
User: "Show me the current view"

Claude uses chimerax_screenshot() → displays image
```

### Bundle Development

```
User: "Test my ChimeraX bundle in ./my-bundle"

Claude uses bundle_test(bundle_path="./my-bundle", smoke=True)
```

## Claude Code Skills

This repository includes Claude Code skills for ChimeraX structural analysis, documentation reference, and bundle development.

### Available Skills

| Skill | Description |
|-------|-------------|
| `/analyze-structure` | Comprehensive structural analysis with report generation |
| `/explore-chimerax` | Router skill - documentation reference and sub-skill routing |
| `/explore-chimerax-commands` | Command exploration and MCP operation reference |
| `/reference-chimerax-dev` | Bundle/extension development reference |

### Installation

Copy the skills to your Claude Code skills directory:

```bash
cp -r skills/* ~/.claude/skills/
```

### Setting Up Documentation

The skills reference local ChimeraX HTML documentation. Create a symlink to your ChimeraX installation's docs:

```bash
# macOS
ln -s /Applications/ChimeraX-1.9.app/Contents/share/docs \
  ~/.claude/skills/explore-chimerax/assets/docs

# Linux (adjust path to your ChimeraX installation)
ln -s /usr/lib/ucsf-chimerax/share/docs \
  ~/.claude/skills/explore-chimerax/assets/docs
```

The pre-built index (`chimerax-1.9.index.json`) is included and covers 149 commands, 13 tutorials, and 16 API modules.

## Requirements

- [UCSF ChimeraX](https://www.cgl.ucsf.edu/chimerax/)
- Python 3.12+
- [echidna](https://github.com/N283T/echidna) (optional, for bundle tools)

## How It Works

This MCP server communicates with ChimeraX via its REST API:

1. ChimeraX is started with `remotecontrol rest start port 63269`
2. Commands are sent via HTTP GET to `http://127.0.0.1:63269/run?command=...`
3. Results are parsed and returned to Claude

## Security Considerations

This MCP server provides powerful capabilities that should be used with caution:

- **Command Execution**: The `chimerax_run` tool can execute arbitrary ChimeraX commands, including:
  - Python code execution via `runscript`
  - Shell commands via `shell`
- **File System Access**: Tools can read and write files accessible to ChimeraX
- **Network Access**: ChimeraX can fetch structures from remote servers

**Recommendations:**
- Only use with trusted AI assistants and prompts
- Run in a sandboxed environment for untrusted use cases
- Review commands before execution in sensitive environments

## License

MIT
