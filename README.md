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
| `chimerax_structure_report` | Compose a structure report with RCSB/PDBe/PDBj/UniProt URL links plus caller-provided UniProt feature annotations mapped to clickable ChimeraX residue links |

`chimerax_rich_log` passes HTML through to ChimeraX with `is_html=True`; only use it with trusted input. `chimerax_rich_report` escapes plain text fields but allows raw HTML blocks for trusted local reports. Use `theme="auto"` to let generated reports follow the ChimeraX/system light or dark appearance where Qt WebEngine supports `prefers-color-scheme`; explicit `theme="light"` and `theme="dark"` remain available. Pass `save_html_path` to either rich-log tool to save the exact generated HTML locally; existing files require `overwrite=true`.

Rich report values can include structured ChimeraX command links without raw HTML. Use `{"text":"#1/P:120", "spec":"#1/P:120", "action":"select"}` for common actions (`select`, `view`, `show`, `hide`, `metadata`) or `{"text":"open view", "command":"view #1/P:120"}` for an explicit command. Links are rendered as `cxcmd:` anchors in the ChimeraX Log. Safe external database links can use `{"text":"P00698", "url":"https://www.uniprot.org/uniprotkb/P00698/entry"}`; only `http` and `https` URLs are linked. By default, rich-report URL links are converted to ChimeraX `runscript` command links that open the URL in the system default browser. Pass `external_link_target="chimerax"` to keep direct HTTP(S) links for ChimeraX's built-in browser/help viewer.

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


## Structure Reports with External Annotations

`chimerax_structure_report` renders a ready-to-read ChimeraX Log report from structure metadata plus optional external annotations. It is designed to pair well with Togo MCP: fetch UniProt/PDB annotations with Togo MCP, normalize them to `external_features`, then pass them to ChimeraX MCP for residue mapping and clickable display.

Example for hen egg-white lysozyme (`PDB 1AKI`, `UniProt P00698`), where the PDB chain is the mature protein and UniProt has signal peptide residues 1-18:

```json
{
  "model_spec": "#1",
  "model_name": "1aki",
  "pdb_id": "1AKI",
  "chain_mappings": [
    {
      "chain_id": "A",
      "uniprot_accession": "P00698",
      "uniprot_start": 19,
      "uniprot_end": 147,
      "pdb_start": 1,
      "pdb_end": 129
    }
  ],
  "external_features": [
    {
      "type": "Active site",
      "uniprot_position": 53,
      "description": "Catalytic residue",
      "source_url": "https://www.uniprot.org/uniprotkb/P00698/entry#feature-viewer"
    }
  ],
  "external_link_target": "system"
}
```

The report includes RCSB, PDBe, PDBj, and UniProt URL links when IDs are provided. Mapped features become ChimeraX command links such as `select #1/A:35` and `view #1/A:35`. External DB/source links open in the system default browser by default; set `external_link_target` to `"chimerax"` if you prefer ChimeraX's internal browser.

Useful Togo MCP / UniProt SPARQL template for feature annotations:

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX faldo: <http://biohackathon.org/resource/faldo#>
PREFIX uniprot: <http://purl.uniprot.org/uniprot/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?annType ?comment ?begin ?end WHERE {
  VALUES ?annType {
    up:Active_Site_Annotation
    up:Binding_Site_Annotation
    up:Metal_Binding_Annotation
    up:Site_Annotation
  }
  uniprot:P00698 up:annotation ?ann .
  ?ann a ?annType .
  OPTIONAL { ?ann rdfs:comment ?comment . }
  OPTIONAL {
    ?ann up:range ?range .
    OPTIONAL { ?range faldo:begin/faldo:position ?begin . }
    OPTIONAL { ?range faldo:end/faldo:position ?end . }
  }
}
ORDER BY ?begin
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
