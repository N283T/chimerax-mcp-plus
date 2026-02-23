# chimerax-mcp-plus

MCP server for controlling UCSF ChimeraX molecular visualization.

## Features

- **ChimeraX Control**: Start, detect, and control ChimeraX via REST API
- **Command Execution**: Run any ChimeraX command
- **Screenshot Capture**: Take screenshots of the 3D view and tool windows
- **View Management**: Fit, rotate, and reset the view
- **Session Management**: Save and load ChimeraX sessions


## Installation

```bash
# Global install (recommended)
uv tool install git+https://github.com/N283T/chimerax-mcp-plus

# Update
uv tool upgrade chimerax-mcp
```

## Configuration

Add to your MCP client configuration (e.g. `~/.claude/.mcp.json`):

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
| `chimerax_screenshot` | Capture screenshot of the 3D view |
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

## Claude Code Skills

This repository includes Claude Code skills for ChimeraX documentation reference and bundle development.

| Skill | Description |
|-------|-------------|
| `/explore-chimerax` | Router skill for ChimeraX documentation and sub-skill routing |
| `/explore-chimerax-commands` | Command exploration and MCP operation reference |
| `/reference-chimerax-dev` | Bundle/extension development reference |

To use these skills, symlink them into your Claude Code skills directory:

```bash
ln -s /path/to/chimerax-mcp-plus/skills/* ~/.claude/skills/
```

## How It Works

This MCP server communicates with ChimeraX via its REST API:

1. ChimeraX is started with `remotecontrol rest start port 63269`
2. Commands are sent via HTTP GET to `http://127.0.0.1:63269/run?command=...`
3. Results are parsed and returned to the AI client

## Requirements

- [UCSF ChimeraX](https://www.cgl.ucsf.edu/chimerax/)
- Python 3.12+

## Security Considerations

This MCP server provides powerful capabilities that should be used with caution:

- **Command Execution**: `chimerax_run` can execute arbitrary ChimeraX commands, including Python code via `runscript` and shell commands via `shell`
- **File System Access**: Tools can read and write files accessible to ChimeraX
- **Network Access**: ChimeraX can fetch structures from remote servers

**Recommendations:**
- Only use with trusted AI assistants and prompts
- Run in a sandboxed environment for untrusted use cases
- Review commands before execution in sensitive environments

## License

MIT
