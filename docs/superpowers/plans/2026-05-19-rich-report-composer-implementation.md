# Rich Report Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain generic `chimerax_rich_report` formatter with a flexible rich block composer that can produce dashboard-like ChimeraX Log HTML.

**Architecture:** Keep `chimerax_rich_log` as the low-level trusted HTML writer. Rework `chimerax_rich_report` so it validates a block list, renders themed inline HTML, and sends the result through the existing hardened `_write_rich_log` path.

**Tech Stack:** Python 3.12, FastMCP, pytest, ruff, ty, ChimeraX Log HTML via `session.logger(..., is_html=True)`.

---

## File Structure

- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`
  - Replace plain report rendering helpers with theme and block-rendering helpers.
  - Replace `chimerax_rich_report` signature with `title`, `subtitle`, `theme`, `accent_color`, `blocks`, and `level`.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`
  - Replace old generic report tests with composer tests for themes, blocks, escaping, raw HTML, validation, and write path.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`
  - Replace old generic report example with block-composer example.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`
  - Note that `chimerax_rich_report` is now a block composer.

---

### Task 1: Replace rich report tests with composer expectations

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Replace `TestRichReport` with composer-focused tests**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`, replace the existing `TestRichReport` class with tests that call the desired new API:

```python
class TestRichReport:
    """Tests for rich report block composer generation and logging."""

    def test_build_rich_report_html_renders_dark_block_composer(self):
        html = _build_rich_report_html(
            title="Carbonic Anhydrase II",
            subtitle="PDB 1CA2 · active-site snapshot",
            theme="dark",
            accent_color="#58a6ff",
            blocks=[
                {
                    "type": "cards",
                    "items": [
                        {"label": "Model", "value": "#1 · 1CA2"},
                        {"label": "Cofactor", "value": "Zn²⁺", "color": "#ffd33d"},
                    ],
                },
                {"type": "heading", "text": "Functional feature map"},
                {
                    "type": "table",
                    "columns": ["Feature", "Residues", "View"],
                    "rows": [
                        ["Active site", "His64", {"text": "red", "style": "background:#da3633;color:white;font-weight:800;"}],
                    ],
                    "header_color": "#1f6feb",
                },
                {"type": "callout", "tone": "warning", "title": "Note", "text": "Draft report"},
            ],
        )

        assert "chimerax-mcp-rich-report" in html
        assert "background:#0d1117" in html
        assert "Carbonic Anhydrase II" in html
        assert "PDB 1CA2 · active-site snapshot" in html
        assert "#1 · 1CA2" in html
        assert "Zn²⁺" in html
        assert "Functional feature map" in html
        assert "background:#da3633;color:white;font-weight:800;" in html
        assert "Draft report" in html

    def test_build_rich_report_html_renders_light_theme(self):
        html = _build_rich_report_html(
            title="Light report",
            theme="light",
            blocks=[{"type": "paragraph", "text": "Readable on white backgrounds"}],
        )

        assert "background:#ffffff" in html
        assert "color:#111827" in html
        assert "Readable on white backgrounds" in html

    def test_build_rich_report_html_escapes_text_but_preserves_raw_html(self):
        html = _build_rich_report_html(
            title="Unsafe <title>",
            theme="dark",
            blocks=[
                {"type": "paragraph", "text": "Text <script>alert(1)</script>"},
                {"type": "html", "html": "<p><b>Trusted raw HTML</b></p>"},
            ],
        )

        assert "Unsafe &lt;title&gt;" in html
        assert "Text &lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<p><b>Trusted raw HTML</b></p>" in html
        assert "Text <script>" not in html

    def test_build_rich_report_html_renders_badges_and_legend(self):
        html = _build_rich_report_html(
            title="Legend report",
            blocks=[
                {"type": "badges", "items": ["interactive", {"label": "view colored", "tone": "success"}]},
                {
                    "type": "legend",
                    "items": [
                        {"label": "Active site", "color": "#da3633", "description": "His64"},
                        {"label": "Zn²⁺ ligands", "color": "#fb8500", "description": "His94/96/119"},
                    ],
                },
            ],
        )

        assert "interactive" in html
        assert "view colored" in html
        assert "Active site" in html
        assert "#da3633" in html
        assert "His94/96/119" in html

    def test_rich_report_rejects_empty_title(self):
        result = chimerax_rich_report.fn(title="  ")
        assert result["status"] == "error"
        assert "title" in result["message"].lower()
        assert "empty" in result["message"].lower()

    def test_rich_report_rejects_invalid_level(self):
        result = chimerax_rich_report.fn(title="Report", level="debug")
        assert result["status"] == "error"
        assert "level" in result["message"].lower()

    def test_rich_report_rejects_invalid_theme(self):
        result = chimerax_rich_report.fn(title="Report", theme="sepia")
        assert result["status"] == "error"
        assert "theme" in result["message"].lower()

    def test_rich_report_rejects_unknown_block_type(self):
        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "timeline"}])
        assert result["status"] == "error"
        assert "blocks[0].type" in result["message"]

    def test_rich_report_rejects_malformed_table_columns_and_rows(self):
        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "table", "columns": 3}])
        assert result["status"] == "error"
        assert "blocks[0].columns" in result["message"]

        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "table", "rows": 3}])
        assert result["status"] == "error"
        assert "blocks[0].rows" in result["message"]

    def test_rich_report_builds_html_and_writes_it(self):
        captured: dict[str, str] = {}

        def fake_write_rich_log(html: str, level: str):
            captured["html"] = html
            captured["level"] = level
            return {"status": "ok", "level": level, "message": "Rich log written"}

        with patch("chimerax_mcp.server._write_rich_log", side_effect=fake_write_rich_log):
            result = chimerax_rich_report.fn(
                title="Analysis Summary",
                subtitle="Composer output",
                theme="dark",
                blocks=[
                    {"type": "cards", "items": [{"label": "Models", "value": 1}]},
                    {"type": "paragraph", "text": "Complete"},
                ],
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}
        assert captured["level"] == "info"
        assert "Analysis Summary" in captured["html"]
        assert "Composer output" in captured["html"]
        assert "Models" in captured["html"]
        assert "Complete" in captured["html"]
```

- [ ] **Step 2: Run composer tests and verify RED**

Run:

```bash
uv run pytest tests/test_server.py::TestRichReport -q
```

Expected: FAIL because the current implementation uses the old plain report signature/renderer.

- [ ] **Step 3: Run lint on tests**

Run:

```bash
uv run ruff check tests/test_server.py
```

Expected: PASS. If ruff reports formatting or simplification issues, fix the tests only.

- [ ] **Step 4: Commit failing composer tests**

Run:

```bash
git add tests/test_server.py
git commit -m "test: define rich report composer behavior"
```

Expected: commit succeeds with only test changes.

---

### Task 2: Implement theme/block composer

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`
- Test: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Add theme/block constants and helpers**

In `server.py`, add constants near `VALID_LOG_LEVELS`:

```python
VALID_RICH_REPORT_THEMES = {"auto", "dark", "light"}
VALID_RICH_REPORT_BLOCK_TYPES = {"heading", "paragraph", "cards", "table", "callout", "badges", "legend", "html"}
```

Add focused helpers before `_build_rich_report_html`:

```python
def _rich_report_theme(theme: str, accent_color: str | None = None) -> dict[str, str]:
    """Return inline color tokens for rich report rendering."""
    normalized = theme.strip().lower()
    if normalized == "light":
        default_accent = accent_color or "#0673c8"
        return {
            "accent": default_accent,
            "bg": "#ffffff",
            "text": "#111827",
            "muted": "#4b5563",
            "panel": "#f8fafc",
            "border": "#cbd5e1",
            "card": "#f8fafc",
            "table_header": default_accent,
            "callout_note_bg": "#eff6ff",
            "callout_note_border": "#2563eb",
            "callout_success_bg": "#ecfdf5",
            "callout_success_border": "#16a34a",
            "callout_warning_bg": "#fffbeb",
            "callout_warning_border": "#d97706",
            "callout_danger_bg": "#fef2f2",
            "callout_danger_border": "#dc2626",
        }
    default_accent = accent_color or "#58a6ff"
    return {
        "accent": default_accent,
        "bg": "#0d1117",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "panel": "#161b22",
        "border": "#30363d",
        "card": "#161b22",
        "table_header": "#1f6feb",
        "callout_note_bg": "#10233f",
        "callout_note_border": "#58a6ff",
        "callout_success_bg": "#0f2a1a",
        "callout_success_border": "#238636",
        "callout_warning_bg": "#2d2302",
        "callout_warning_border": "#d29922",
        "callout_danger_bg": "#3d1117",
        "callout_danger_border": "#da3633",
    }
```

- [ ] **Step 2: Add block validation**

Add:

```python
def _validate_rich_report_blocks(blocks: list[dict[str, Any]] | None) -> str | None:
    """Validate rich report blocks and return an error message, if invalid."""
    if blocks is None:
        return None
    if not isinstance(blocks, list):
        return "blocks must be a list"
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            return f"blocks[{index}] must be an object"
        block_type = str(block.get("type", "")).strip().lower()
        if block_type not in VALID_RICH_REPORT_BLOCK_TYPES:
            return (
                f"blocks[{index}].type must be one of: "
                f"{', '.join(sorted(VALID_RICH_REPORT_BLOCK_TYPES))}"
            )
        if block_type == "table":
            columns = block.get("columns", [])
            rows = block.get("rows", [])
            if not isinstance(columns, (list, tuple)):
                return f"blocks[{index}].columns must be a list"
            if not isinstance(rows, (list, tuple)):
                return f"blocks[{index}].rows must be a list"
        if block_type in {"cards", "badges", "legend"}:
            items = block.get("items", [])
            if not isinstance(items, (list, tuple)):
                return f"blocks[{index}].items must be a list"
    return None
```

- [ ] **Step 3: Replace report render helpers with block renderers**

Implement helpers for each block type. Use escaped text by default; preserve raw `html` fields:

```python
def _rich_report_text_or_html(block: dict[str, Any], field: str = "text") -> str:
    if block.get("html") is not None:
        return str(block["html"])
    return _escape_html_value(block.get(field, ""))
```

Add render helpers named `_render_rich_report_heading`, `_render_rich_report_paragraph`, `_render_rich_report_cards`, `_render_rich_report_table`, `_render_rich_report_callout`, `_render_rich_report_badges`, `_render_rich_report_legend`, and `_render_rich_report_block`.

The renderers should use inline CSS matching the smoke-test HTML style: container panels, visible borders, table headers, badges, callout border-left, and grid cards. Keep each helper small and deterministic.

- [ ] **Step 4: Replace `_build_rich_report_html` signature and body**

Replace old `_build_rich_report_html` with:

```python
def _build_rich_report_html(
    title: str,
    subtitle: str | None = None,
    theme: str = "auto",
    accent_color: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Build themed rich report HTML for the ChimeraX Log."""
```

The body should:

- compute `tokens = _rich_report_theme(theme, accent_color)`
- render a top-level `<div class="chimerax-mcp-rich-report" ...>` with explicit background/text/border/radius/padding/max-width
- render a small uppercase label, `<h1>`, optional subtitle, and accent border
- render every block in order using `_render_rich_report_block`
- close the container

- [ ] **Step 5: Replace `chimerax_rich_report` signature/body**

Replace old tool signature with:

```python
@mcp.tool()
def chimerax_rich_report(
    title: str,
    subtitle: str | None = None,
    theme: str = "auto",
    accent_color: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    level: str = "info",
) -> dict[str, Any]:
```

Behavior:

- validate title non-empty
- validate level using `_validate_log_level`
- validate `theme` in `VALID_RICH_REPORT_THEMES`
- validate blocks using `_validate_rich_report_blocks`
- build HTML and call `_write_rich_log`

- [ ] **Step 6: Run tests and lint**

Run:

```bash
uv run pytest tests/test_server.py::TestRichLog tests/test_server.py::TestRichReport -q
uv run ruff check src/chimerax_mcp/server.py tests/test_server.py
uv run ty check src/chimerax_mcp/server.py tests/test_server.py
```

Expected: all pass.

- [ ] **Step 7: Commit composer implementation**

Run:

```bash
git add src/chimerax_mcp/server.py tests/test_server.py
git commit -m "feat: replace rich report with block composer"
```

---

### Task 3: Update docs for composer API

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`

- [ ] **Step 1: Update README tool description**

In README, change the `chimerax_rich_report` description to:

```markdown
| `chimerax_rich_report` | Compose a themed rich HTML report from flexible blocks such as cards, tables, badges, callouts, legends, and raw HTML |
```

Update the note to say raw HTML blocks are trusted local input.

- [ ] **Step 2: Replace README generic report example**

Replace the old generic report JSON example with a block-composer example:

```json
{
  "title": "Carbonic Anhydrase II active-site snapshot",
  "subtitle": "PDB 1CA2 · Zn²⁺ metalloenzyme",
  "theme": "dark",
  "accent_color": "#58a6ff",
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
        ["Active-site shuttle", "His64", {"text": "red", "style": "background:#da3633;color:white;font-weight:800;"}],
        ["Zn²⁺ ligands", "His94, His96, His119", {"text": "orange", "style": "background:#fb8500;color:white;font-weight:800;"}]
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

- [ ] **Step 3: Update changelog**

Add under `[Unreleased]` Added or Changed:

```markdown
- Reworked `chimerax_rich_report()` into a themed block composer for dashboard-like ChimeraX Log output.
```

- [ ] **Step 4: Verify docs diff and commit**

Run:

```bash
git diff -- README.md CHANGELOG.md
git diff --check -- README.md CHANGELOG.md
git add README.md CHANGELOG.md
git commit -m "docs: document rich report composer"
```

---

### Task 4: Final verification and live smoke test

**Files:**
- Verify: repository and MCP behavior

- [ ] **Step 1: Run focused verification with ChimeraX stopped**

Run:

```bash
uv run pytest tests/test_server.py tests/test_chimerax.py -q
uv run ruff check src tests
uv run ty check src tests
```

Expected: all pass. If ChimeraX is running, stop it first because some existing tests assume not-running behavior.

- [ ] **Step 2: Reconnect MCP server if needed**

Because the user installed this package via editable `uv tool`, code changes are picked up by new MCP server processes. Reconnect/restart the MCP server process before live testing.

- [ ] **Step 3: Live smoke test**

With ChimeraX running, call `chimerax_rich_report` with a dark block-composer payload similar to the README example. Expected MCP result:

```json
{"status": "ok", "level": "info", "message": "Rich log written"}
```

- [ ] **Step 4: Inspect status**

Run:

```bash
git status --short --branch
```

Expected: clean tracked tree; pre-existing untracked `.codex/` may remain and should not be added.
