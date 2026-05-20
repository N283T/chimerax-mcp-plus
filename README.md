# chimerax-mcp-plus

MCP server for controlling UCSF ChimeraX molecular visualization.

## Features

- **ChimeraX Control**: Start, detect, and control ChimeraX via REST API
- **Command Execution**: Run any ChimeraX command
- **Screenshot Capture**: Take screenshots of the 3D view and tool windows
- **Rich Log Output**: Write trusted HTML and generated analysis reports to the ChimeraX Log
- **API Reference**: Search packaged/local ChimeraX docs and inspect live Python API symbols via safe `runscript` helpers
- **Script Recipes**: Search bundled `runscript` Python patterns, including JSON and rich-report payload examples
- **View Management**: Fit, rotate, and reset the view
- **Session Management**: Save and load ChimeraX sessions


## Installation

```bash
# Global install (recommended)
uv tool install git+https://github.com/N283T/chimerax-mcp-plus

# Update
uv tool upgrade chimerax-mcp-plus
```

## Configuration

Add to your MCP client configuration (e.g. `~/.claude/.mcp.json`):

```json
{
  "mcpServers": {
    "chimerax": {
      "command": "chimerax-mcp-plus"
    }
  }
}
```

### Specifying a ChimeraX version

By default, the server auto-detects the latest installed ChimeraX. To use a specific version, set the `CHIMERAX_PATH` environment variable:

```json
{
  "mcpServers": {
    "chimerax": {
      "command": "chimerax-mcp-plus",
      "env": {
        "CHIMERAX_PATH": "/Applications/ChimeraX-1.9.app/Contents/MacOS/ChimeraX"
      }
    }
  }
}
```

## Available Tools

### ChimeraX Control

| Tool | Description |
|------|-------------|
| `chimerax_detect` | Detect ChimeraX installation |
| `chimerax_start` | Start ChimeraX with REST API enabled (supports `background` and optional `include_version` mode) |
| `chimerax_stop` | Stop the ChimeraX process |
| `chimerax_status` | Check if ChimeraX is running without logging `version` unless `include_version=true` |
| `chimerax_run` | Execute any ChimeraX command |
| `chimerax_models` | List open models |

### Screenshot Management

| Tool | Description |
|------|-------------|
| `chimerax_screenshot` | Capture screenshot of the 3D view |
| `chimerax_tool_screenshot` | Capture screenshot of a tool window |
| `chimerax_list_screenshots` | List all saved screenshots |
| `chimerax_cleanup_screenshots` | Delete old screenshots (e.g., `older_than_days=7`) |

### Rich Log Output

| Tool | Description |
|------|-------------|
| `chimerax_rich_log` | Write trusted caller-provided HTML to the ChimeraX Log, optionally saving the generated HTML |
| `chimerax_rich_report` | Compose a themed rich HTML report from flexible blocks such as cards, tables, progress bars, columns, badges, callouts, legends, and raw HTML |

`chimerax_rich_log` passes HTML through to ChimeraX with `is_html=True`; only use it with trusted input. `chimerax_rich_report` escapes plain text fields but allows raw HTML blocks for trusted local reports. Use `theme="auto"` to let generated reports follow the ChimeraX/system light or dark appearance where Qt WebEngine supports `prefers-color-scheme`; explicit `theme="light"` and `theme="dark"` remain available. Pass `save_html_path` to either rich-log tool to save the exact generated HTML locally; existing files require `overwrite=true`.

Rich report values can include structured ChimeraX command links without raw HTML. Use `{"text":"#1/P:120", "spec":"#1/P:120", "action":"select"}` for common actions (`select`, `view`, `show`, `hide`, `metadata`) or `{"text":"open view", "command":"view #1/P:120"}` for an explicit command. Links are rendered as `cxcmd:` anchors in the ChimeraX Log.

### API Reference and Python Introspection

| Tool | Description |
|------|-------------|
| `chimerax_api_search` | Search static ChimeraX command, tutorial, and Python API module metadata; works without optional skills by using a packaged lightweight index |
| `chimerax_api_read` | Read a static documentation entry from local docs when available, or return the packaged metadata summary |
| `chimerax_python_inspect` | Inspect a live ChimeraX Python API symbol via `runscript` using bounded `inspect` output |
| `chimerax_python_dir` | List attributes of a live ChimeraX Python API symbol with optional substring filtering |

Static lookup uses `CHIMERAX_DOCS_PATH` first, then detected local ChimeraX docs, then repository-local skill docs when running from a checkout, and finally the packaged fallback index. Live introspection requires ChimeraX to be running and accepts only dotted symbols such as `chimerax.atomic.AtomicStructure`; it does not expose arbitrary Python evaluation.

### Script Recipes

| Tool | Description |
|------|-------------|
| `chimerax_script_recipe_search` | Search bundled ChimeraX `runscript` Python recipes by query, category, and output kind |
| `chimerax_script_recipe_read` | Read a bundled recipe, including metadata, related API queries, optional official references, and the script body |

Recipes are static examples and are not executed by these tools. They are intended to help an LLM write trusted ChimeraX Python scripts after consulting `chimerax_api_read` or `chimerax_python_inspect`. Some recipes emit `CHIMERAX_MCP_RESULT_JSON=...` marker lines for downstream parsing; recipes with `output_kind="rich_report_payload"` produce payloads shaped for `chimerax_rich_report`. Official RBVI ChimeraX Recipes are referenced as links where useful, but this package bundles its own short MCP-oriented examples.

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
| `/explore-chimerax` | ChimeraX command exploration and documentation reference |
| `/reference-chimerax-dev` | Bundle/extension development reference |

To use these skills, symlink them into your Claude Code skills directory:

```bash
ln -s /path/to/chimerax-mcp-plus/skills/* ~/.claude/skills/
```

## Claude Code Agents

This repository includes specialized agents for ChimeraX workflows.

| Agent | Description |
|--------|-------------|
| `chimerax-operator` | MCP operator for molecular visualization and manipulation |
| `structural-biologist` | Structural biology expert for protein and molecular analysis |
| `chimerax-developer` | Bundle and extension developer using echidna |

To use these agents, symlink them into your Claude Code agents directory:

```bash
ln -s /path/to/chimerax-mcp-plus/.claude/agents/* ~/.claude/agents/
```

## How It Works

This MCP server communicates with ChimeraX via its REST API:

1. ChimeraX is started with `remotecontrol rest start port 63269 json true log true`
2. Commands are sent via HTTP GET to `http://127.0.0.1:63269/run?command=...`
3. Running-state checks use `http://127.0.0.1:63269/cmdline.html` so routine MCP calls do not spam the ChimeraX Log with `version`
4. Results are parsed and returned to the AI client

## Rich Log Examples

Low-level trusted HTML:

```json
{
  "html": "<p><b>RMSD:</b> 1.42 Å</p>",
  "title": "Alignment summary"
}
```

Themed block-composer report:

```json
{
  "title": "Carbonic Anhydrase II active-site snapshot",
  "subtitle": "PDB 1CA2 · Zn²⁺ metalloenzyme",
  "theme": "auto",
  "accent_color": "#58a6ff",
  "save_html_path": "/tmp/ca2-report.html",
  "blocks": [
    {
      "type": "cards",
      "items": [
        {"label": "Model", "value": "#1 · 1CA2"},
        {"label": "Resolution", "value": "2.0 Å"},
        {"label": "Cofactor", "value": "Zn²⁺", "color": "#ffd33d"}
      ]
    },
    {
      "type": "table",
      "title": "Functional feature map",
      "columns": ["Feature", "Residues", "View"],
      "rows": [
        [
          "Active-site shuttle",
          "His64",
          {"text": "red", "style": "background:#da3633;color:white;font-weight:800;"}
        ],
        [
          "Zn²⁺ ligands",
          "His94, His96, His119",
          {"text": "orange", "style": "background:#fb8500;color:white;font-weight:800;"}
        ]
      ]
    },
    {
      "type": "progress",
      "label": "Active-site completeness",
      "value": 4,
      "max": 4,
      "color": "#238636"
    },
    {
      "type": "columns",
      "items": [
        {"type": "paragraph", "text": "Left column narrative."},
        {"type": "paragraph", "text": "Right column notes."}
      ]
    },
    {
      "type": "callout",
      "tone": "warning",
      "title": "Note",
      "text": "Raw HTML blocks are allowed for trusted local reports."
    }
  ]
}
```



Structured command-link table cell:

```json
{
  "type": "table",
  "title": "Clickable residues",
  "columns": ["Model", "Residue", "Action"],
  "rows": [
    [
      {"text": "#1", "spec": "#1", "action": "select"},
      {"text": "P:120", "spec": "#1/P:120", "action": "select"},
      {"text": "view", "spec": "#1/P:120", "action": "view"}
    ]
  ]
}
```

## Script Recipe Examples

Find recipes that produce rich-report payloads:

```json
{
  "query": "structure summary",
  "category": "rich_report",
  "output_kind": "rich_report_payload",
  "limit": 5
}
```

Read the recipe script:

```json
{
  "recipe_id": "structure_summary_rich_report_payload",
  "include_script": true,
  "max_chars": 8000
}
```

A rich-report recipe emits a `CHIMERAX_MCP_RESULT_JSON=` line containing a payload with `title` and `blocks`. After extracting that payload, pass it to `chimerax_rich_report` to display a styled report in the ChimeraX Log.

## API Reference Examples

Search packaged or local ChimeraX API metadata:

```json
{
  "query": "AtomicStructure residues",
  "kind": "modules",
  "limit": 5
}
```

Read a static documentation entry:

```json
{
  "target": "atomic",
  "max_chars": 4000
}
```

Inspect a live ChimeraX Python API symbol:

```json
{
  "symbol": "chimerax.atomic.AtomicStructure",
  "include_dir": true,
  "max_doc_chars": 4000
}
```

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
