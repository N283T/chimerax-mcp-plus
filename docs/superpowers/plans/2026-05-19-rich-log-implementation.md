# Rich Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MCP tools that write arbitrary HTML and generated generic reports to the ChimeraX Log.

**Architecture:** Keep all implementation in the existing FastMCP server module and reuse the established temporary-script plus ChimeraX REST `runscript` pattern. The low-level rich log tool passes trusted HTML through with `is_html=True`; the report tool builds escaped, styled HTML before calling the same execution helper.

**Tech Stack:** Python 3.12, FastMCP, httpx, pytest, ruff, ty, ChimeraX REST API, ChimeraX `session.logger` HTML logging API.

---

## File Structure

- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`
  - Add rich log constants, validators, HTML builders, ChimeraX script builder, execution helper, and two MCP tools.
  - Keep the helpers near existing command/script helpers so the file follows current conventions.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`
  - Import new helpers/tools.
  - Add focused tests for validation, script generation, report escaping/rendering, and mocked happy/error paths.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`
  - Document the new Rich Log tools and trusted HTML warning.
- Modify `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`
  - Add the rich log tools under `[Unreleased]`.

---

### Task 1: Add failing rich log unit tests

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Extend imports for the new rich log symbols**

Add these names to the existing `from chimerax_mcp.server import (...)` block in `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`:

```python
    VALID_LOG_LEVELS,
    _build_rich_log_html,
    _build_rich_log_script,
    _build_rich_report_html,
    chimerax_rich_log,
    chimerax_rich_report,
```

- [ ] **Step 2: Add tests for low-level rich logging**

Append this test class to `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py` before the final end of file:

```python
class TestRichLog:
    """Tests for chimerax_rich_log and helper script generation."""

    def test_valid_log_levels(self):
        assert VALID_LOG_LEVELS == {"error", "info", "warning"}

    def test_rich_log_rejects_empty_html(self):
        result = chimerax_rich_log.fn(html="   ")
        assert result["status"] == "error"
        assert "html" in result["message"].lower()
        assert "empty" in result["message"].lower()

    def test_rich_log_rejects_invalid_level(self):
        result = chimerax_rich_log.fn(html="<b>Hello</b>", level="debug")
        assert result["status"] == "error"
        assert "level" in result["message"].lower()
        assert "error, info, warning" in result["message"]

    def test_rich_log_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<b>Hello</b>")

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_build_rich_log_html_adds_optional_title(self):
        html = _build_rich_log_html("<p>Body</p>", title="Analysis <One>")
        assert "chimerax-mcp-rich-log" in html
        assert "Analysis &lt;One&gt;" in html
        assert "<p>Body</p>" in html

    def test_build_rich_log_html_without_title_keeps_html(self):
        assert _build_rich_log_html("<em>Body</em>") == "<em>Body</em>"

    def test_build_rich_log_script_uses_html_logger_and_thread_safe(self):
        script = _build_rich_log_script("<p>Hello</p>", "warning")
        assert "html_content = '<p>Hello</p>'" in script
        assert "logger_method = session.logger.warning" in script
        assert "is_html=True" in script
        assert "session.ui.thread_safe(write_log)" in script
        assert "write_log()" in script
        assert "OK: rich log written" in script

    def test_rich_log_sends_runscript_when_running(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run_command(cmd: str):
            commands_run.append(cmd)
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": ["OK: rich log written"]},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(
                html="<strong>Result</strong>", level="info", title="Summary"
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}
        assert len(commands_run) == 1
        assert commands_run[0].startswith("runscript ")

    def test_rich_log_returns_script_error(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": ["ERROR: boom"]},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>Hi</p>")

        assert result == {"status": "error", "message": "boom"}
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run:

```bash
uv run pytest tests/test_server.py::TestRichLog -q
```

Expected: FAIL during collection/import because `VALID_LOG_LEVELS`, `_build_rich_log_html`, `_build_rich_log_script`, `chimerax_rich_log`, and related symbols are not implemented yet.

- [ ] **Step 4: Commit the failing tests**

Run:

```bash
git add tests/test_server.py
git commit -m "test: add rich log coverage"
```

Expected: commit succeeds with only test changes.

---

### Task 2: Implement low-level rich HTML logging

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`
- Test: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Add the standard-library HTML import**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`, add this import beside the existing standard-library imports:

```python
import html as html_lib
```

- [ ] **Step 2: Add rich log constants near existing validation constants**

Add this constant after `VALID_AXES`:

```python
VALID_LOG_LEVELS = {"error", "info", "warning"}
```

- [ ] **Step 3: Add rich log helper functions**

Add these helpers after `_run_command()` and before the first user-facing command helper group:

```python
def _validate_log_level(level: str) -> str | None:
    """Normalize and validate a ChimeraX logger level."""
    normalized = level.strip().lower()
    if normalized not in VALID_LOG_LEVELS:
        return None
    return normalized


def _build_rich_log_html(html: str, title: str | None = None) -> str:
    """Wrap trusted caller-provided HTML with an optional escaped title."""
    if title is None or not title.strip():
        return html
    escaped_title = html_lib.escape(title.strip())
    return "\n".join(
        [
            '<div class="chimerax-mcp-rich-log" '
            'style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; '
            'line-height: 1.35; margin: 0.4em 0;">',
            f'<h2 style="margin: 0 0 0.35em 0; font-size: 1.25em;">{escaped_title}</h2>',
            html,
            "</div>",
        ]
    )


def _build_rich_log_script(html: str, level: str) -> str:
    """Build a ChimeraX Python script that writes HTML to the Log."""
    lines = [
        f"html_content = {html!r}",
        f"level = {level!r}",
        "",
        "def write_log():",
        "    logger_method = getattr(session.logger, level)",
        "    logger_method(html_content, is_html=True)",
        "",
        "try:",
        "    ui = getattr(session, 'ui', None)",
        "    if ui is not None and getattr(ui, 'is_gui', False) and hasattr(ui, 'thread_safe'):",
        "        session.ui.thread_safe(write_log)",
        "    else:",
        "        write_log()",
        "    session.logger.info('OK: rich log written')",
        "except Exception as exc:",
        "    session.logger.info('ERROR: ' + str(exc))",
    ]
    return "\n".join(lines)


def _write_rich_log(html: str, level: str) -> dict[str, Any]:
    """Execute rich HTML logging inside ChimeraX."""
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    script = _build_rich_log_script(html=html, level=level)
    fd, script_path_str = tempfile.mkstemp(suffix=".py", prefix="chimerax_rich_log_")
    os.close(fd)
    script_path = Path(script_path_str)
    try:
        script_path.write_text(script)
        result = client.run_command(f"runscript {script_path}")
        output = client._extract_output(result)

        if "ERROR:" in output:
            msg = output.split("ERROR:", 1)[1].strip()
            return {"status": "error", "message": msg}

        if "OK: rich log written" in output:
            return {"status": "ok", "level": level, "message": "Rich log written"}

        return {"status": "error", "message": f"Unexpected output: {output}"}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    finally:
        with contextlib.suppress(OSError):
            script_path.unlink()
```

- [ ] **Step 4: Add the MCP tool function**

Add this tool after `chimerax_run()`:

```python
@mcp.tool()
def chimerax_rich_log(
    html: str,
    level: str = "info",
    title: str | None = None,
) -> dict[str, Any]:
    """Write trusted HTML to the ChimeraX Log.

    SECURITY NOTE: This tool passes caller-provided HTML through to ChimeraX
    with ``is_html=True``. Only use with trusted input.

    Args:
        html: HTML content to write to the ChimeraX Log.
        level: Log level - ``info``, ``warning``, or ``error`` (default: info).
        title: Optional escaped heading displayed above the HTML.

    Returns:
        Status of the rich log write operation.
    """
    if not html or not html.strip():
        return {"status": "error", "message": "html must not be empty"}

    normalized_level = _validate_log_level(level)
    if normalized_level is None:
        return {
            "status": "error",
            "message": f"level must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}",
        }

    rich_html = _build_rich_log_html(html=html, title=title)
    return _write_rich_log(html=rich_html, level=normalized_level)
```

- [ ] **Step 5: Run the low-level tests**

Run:

```bash
uv run pytest tests/test_server.py::TestRichLog -q
```

Expected: all `TestRichLog` tests pass.

- [ ] **Step 6: Run ruff on touched files**

Run:

```bash
uv run ruff check src/chimerax_mcp/server.py tests/test_server.py
```

Expected: PASS. If ruff reports import ordering, run `uv run ruff check --fix src/chimerax_mcp/server.py tests/test_server.py` and inspect the diff.

- [ ] **Step 7: Commit low-level rich log implementation**

Run:

```bash
git add src/chimerax_mcp/server.py tests/test_server.py
git commit -m "feat: add rich HTML logging"
```

Expected: commit succeeds with server and test changes.

---

### Task 3: Add failing generic rich report tests

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Add report tests**

Append this test class after `TestRichLog` in `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`:

```python
class TestRichReport:
    """Tests for generic rich report generation and logging."""

    def test_build_rich_report_html_escapes_data_values(self):
        html = _build_rich_report_html(
            title="Model <One>",
            summary="Contains <script>alert(1)</script>",
            sections=[{"heading": "Section <A>", "body": "Body <unsafe>"}],
            key_values={"Ligand <id>": "ATP <5>"},
            warnings=["Check <distance>"],
            tables=[
                {
                    "title": "Contacts <table>",
                    "columns": ["Atom <1>", "Distance"],
                    "rows": [["CA <A>", 3.2], ["CB", None]],
                }
            ],
        )

        assert "Model &lt;One&gt;" in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "Section &lt;A&gt;" in html
        assert "Body &lt;unsafe&gt;" in html
        assert "Ligand &lt;id&gt;" in html
        assert "ATP &lt;5&gt;" in html
        assert "Check &lt;distance&gt;" in html
        assert "Contacts &lt;table&gt;" in html
        assert "Atom &lt;1&gt;" in html
        assert "CA &lt;A&gt;" in html
        assert "<script>" not in html

    def test_build_rich_report_html_renders_report_structure(self):
        html = _build_rich_report_html(
            title="Analysis Summary",
            summary="Two models compared.",
            sections=[{"heading": "Alignment", "body": "RMSD is 1.4 Å."}],
            key_values={"Models": 2, "Method": "matchmaker"},
            warnings=["One chain was missing."],
            tables=[{"title": "Distances", "columns": ["Pair", "Å"], "rows": [["A-B", 2.8]]}],
        )

        assert "chimerax-mcp-rich-report" in html
        assert "Analysis Summary" in html
        assert "Two models compared." in html
        assert "Alignment" in html
        assert "RMSD is 1.4 Å." in html
        assert "Models" in html
        assert "matchmaker" in html
        assert "One chain was missing." in html
        assert "Distances" in html
        assert "A-B" in html

    def test_rich_report_rejects_empty_title(self):
        result = chimerax_rich_report.fn(title="  ")
        assert result["status"] == "error"
        assert "title" in result["message"].lower()
        assert "empty" in result["message"].lower()

    def test_rich_report_rejects_invalid_level(self):
        result = chimerax_rich_report.fn(title="Report", level="debug")
        assert result["status"] == "error"
        assert "level" in result["message"].lower()

    def test_rich_report_sends_runscript_when_running(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run_command(cmd: str):
            commands_run.append(cmd)
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": ["OK: rich log written"]},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_report.fn(
                title="Analysis Summary",
                summary="Complete",
                key_values={"Models": 1},
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}
        assert len(commands_run) == 1
        assert commands_run[0].startswith("runscript ")
```

- [ ] **Step 2: Run report tests to verify they fail**

Run:

```bash
uv run pytest tests/test_server.py::TestRichReport -q
```

Expected: FAIL because `_build_rich_report_html` and `chimerax_rich_report` are not implemented yet.

- [ ] **Step 3: Commit failing report tests**

Run:

```bash
git add tests/test_server.py
git commit -m "test: add rich report coverage"
```

Expected: commit succeeds with test changes.

---

### Task 4: Implement generic rich report generation

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`
- Test: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/tests/test_server.py`

- [ ] **Step 1: Add small HTML escape helpers**

Add these helpers below `_build_rich_log_html()`:

```python
def _escape_html_value(value: Any) -> str:
    """Escape a value for insertion into generated rich report HTML."""
    if value is None:
        return ""
    return html_lib.escape(str(value))


def _render_rich_report_table(table: dict[str, Any]) -> str:
    """Render one escaped table for a rich report."""
    title = _escape_html_value(table.get("title", ""))
    columns = table.get("columns") or []
    rows = table.get("rows") or []

    header_cells = "".join(
        f'<th style="text-align: left; border-bottom: 1px solid #d0d7de; padding: 0.35em 0.5em;">{_escape_html_value(column)}</th>'
        for column in columns
    )
    body_rows = []
    for row in rows:
        cells = row if isinstance(row, list | tuple) else [row]
        body_cells = "".join(
            f'<td style="border-bottom: 1px solid #eaeef2; padding: 0.35em 0.5em;">{_escape_html_value(cell)}</td>'
            for cell in cells
        )
        body_rows.append(f"<tr>{body_cells}</tr>")

    parts = ['<div class="chimerax-mcp-rich-report-table" style="margin-top: 0.75em;">']
    if title:
        parts.append(f'<h4 style="margin: 0 0 0.35em 0;">{title}</h4>')
    parts.extend(
        [
            '<table style="border-collapse: collapse; width: 100%; font-size: 0.95em;">',
            f"<thead><tr>{header_cells}</tr></thead>",
            f"<tbody>{''.join(body_rows)}</tbody>",
            "</table>",
            "</div>",
        ]
    )
    return "\n".join(parts)
```

- [ ] **Step 2: Add the report HTML builder**

Add this helper below `_render_rich_report_table()`:

```python
def _build_rich_report_html(
    title: str,
    summary: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    key_values: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Build escaped generic report HTML for the ChimeraX Log."""
    parts = [
        '<div class="chimerax-mcp-rich-report" '
        'style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; '
        'line-height: 1.4; border: 1px solid #d0d7de; border-radius: 8px; '
        'padding: 0.85em 1em; margin: 0.5em 0; background: #f6f8fa;">',
        f'<h2 style="margin: 0 0 0.45em 0; font-size: 1.3em;">{_escape_html_value(title.strip())}</h2>',
    ]

    if summary:
        parts.append(
            f'<p style="margin: 0 0 0.8em 0;">{_escape_html_value(summary)}</p>'
        )

    if key_values:
        parts.append('<dl style="display: grid; grid-template-columns: max-content 1fr; gap: 0.25em 0.8em; margin: 0 0 0.8em 0;">')
        for key, value in key_values.items():
            parts.append(f'<dt style="font-weight: 600;">{_escape_html_value(key)}</dt>')
            parts.append(f"<dd style=\"margin: 0;\">{_escape_html_value(value)}</dd>")
        parts.append("</dl>")

    if warnings:
        parts.append('<div style="border-left: 4px solid #d29922; padding: 0.4em 0.7em; margin: 0.7em 0; background: #fff8c5;">')
        parts.append('<strong>Warnings</strong>')
        parts.append('<ul style="margin: 0.35em 0 0 1.2em; padding: 0;">')
        for warning in warnings:
            parts.append(f"<li>{_escape_html_value(warning)}</li>")
        parts.append("</ul></div>")

    for section in sections or []:
        heading = _escape_html_value(section.get("heading", ""))
        body = _escape_html_value(section.get("body", ""))
        parts.append('<section style="margin-top: 0.8em;">')
        if heading:
            parts.append(f'<h3 style="margin: 0 0 0.3em 0; font-size: 1.08em;">{heading}</h3>')
        if body:
            parts.append(f'<p style="margin: 0;">{body}</p>')
        parts.append("</section>")

    for table in tables or []:
        parts.append(_render_rich_report_table(table))

    parts.append("</div>")
    return "\n".join(parts)
```

- [ ] **Step 3: Add the MCP report tool**

Add this tool immediately after `chimerax_rich_log()`:

```python
@mcp.tool()
def chimerax_rich_report(
    title: str,
    summary: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    key_values: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    level: str = "info",
) -> dict[str, Any]:
    """Write a generated generic HTML report to the ChimeraX Log.

    Data-derived values are escaped before insertion into the generated HTML.

    Args:
        title: Report title.
        summary: Optional short report summary.
        sections: Optional list of section dicts with ``heading`` and ``body``.
        tables: Optional list of table dicts with ``title``, ``columns``, and ``rows``.
        key_values: Optional mapping of labels to values for summary facts.
        warnings: Optional warning strings to render as callouts.
        level: Log level - ``info``, ``warning``, or ``error`` (default: info).

    Returns:
        Status of the rich report write operation.
    """
    if not title or not title.strip():
        return {"status": "error", "message": "title must not be empty"}

    normalized_level = _validate_log_level(level)
    if normalized_level is None:
        return {
            "status": "error",
            "message": f"level must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}",
        }

    report_html = _build_rich_report_html(
        title=title,
        summary=summary,
        sections=sections,
        tables=tables,
        key_values=key_values,
        warnings=warnings,
    )
    return _write_rich_log(html=report_html, level=normalized_level)
```

- [ ] **Step 4: Run report tests**

Run:

```bash
uv run pytest tests/test_server.py::TestRichReport -q
```

Expected: all `TestRichReport` tests pass.

- [ ] **Step 5: Run all server tests**

Run:

```bash
uv run pytest tests/test_server.py -q
```

Expected: all tests in `tests/test_server.py` pass.

- [ ] **Step 6: Commit report implementation**

Run:

```bash
git add src/chimerax_mcp/server.py tests/test_server.py
git commit -m "feat: add generic rich reports"
```

Expected: commit succeeds.

---

### Task 5: Update README and changelog

**Files:**
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`
- Modify: `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`

- [ ] **Step 1: Update README feature list**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`, add this bullet under the existing Features list:

```markdown
- **Rich Log Output**: Write trusted HTML and generated analysis reports to the ChimeraX Log
```

- [ ] **Step 2: Add README tool table section**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`, add this section after “Screenshot Management” and before “View Management”:

```markdown
### Rich Log Output

| Tool | Description |
|------|-------------|
| `chimerax_rich_log` | Write trusted caller-provided HTML to the ChimeraX Log |
| `chimerax_rich_report` | Render a generic escaped HTML report from title, summary, sections, tables, key-values, and warnings |

`chimerax_rich_log` passes HTML through to ChimeraX with `is_html=True`; only use it with trusted input. Use `chimerax_rich_report` for structured analysis data that should be escaped before display.
```

- [ ] **Step 3: Add README examples**

Add this subsection after the “How It Works” list in `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`:

```markdown
## Rich Log Examples

Low-level trusted HTML:

```json
{
  "html": "<p><b>RMSD:</b> 1.42 Å</p>",
  "title": "Alignment summary"
}
```

Generic report:

```json
{
  "title": "Structure analysis",
  "summary": "Two chains were analyzed.",
  "key_values": {"Models": 1, "Chains": 2},
  "warnings": ["One ligand is missing density."],
  "tables": [
    {
      "title": "Contacts",
      "columns": ["Atom A", "Atom B", "Distance Å"],
      "rows": [["A:LYS 12 NZ", "B:ASP 45 OD1", 2.9]]
    }
  ]
}
```
```

Important: when inserting this Markdown, close and reopen fences correctly so the outer document renders. The final README should contain two JSON fenced blocks and no accidental nested unclosed fence.

- [ ] **Step 4: Update changelog**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`, add these bullets under the first `[Unreleased]` “Added” heading:

```markdown
- `chimerax_rich_log()` to write trusted HTML directly to the ChimeraX Log.
- `chimerax_rich_report()` to render escaped generic analysis reports in the ChimeraX Log.
```

- [ ] **Step 5: Run README/changelog diff review**

Run:

```bash
git diff -- README.md CHANGELOG.md
```

Expected: diff only documents rich log behavior and does not alter unrelated sections.

- [ ] **Step 6: Commit documentation updates**

Run:

```bash
git add README.md CHANGELOG.md
git commit -m "docs: document rich log tools"
```

Expected: commit succeeds.

---

### Task 6: Final verification and cleanup

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_server.py tests/test_chimerax.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run:

```bash
uv run ruff check src tests
```

Expected: PASS.

- [ ] **Step 3: Run ty**

Run:

```bash
uv run ty check src tests
```

Expected: PASS. If existing project type issues unrelated to this change appear, record the exact output in the final handoff instead of hiding it.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: on `codex/feat-rich-log`; no unstaged tracked changes. The pre-existing untracked `.codex/` directory may still appear and should not be added.

- [ ] **Step 5: Final commit if verification forced small fixes**

If Steps 1-3 required small fixes, commit them:

```bash
git add src/chimerax_mcp/server.py tests/test_server.py README.md CHANGELOG.md
git commit -m "fix: polish rich log implementation"
```

Expected: commit succeeds only if there were tracked fixes. If no fixes were needed, skip this step.
