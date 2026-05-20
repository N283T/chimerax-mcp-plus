# Repository Instructions for Codex

This repository contains `chimerax-mcp-plus`, a Python MCP server for controlling UCSF ChimeraX.

## Scope

- Keep this repository focused on the MCP server package, tests, documentation, and release notes.
- Do not add personal assistant artifacts such as `.codex/`, `.claude/agents/`, `skills/`, or `docs/superpowers/` to the repository.
- Do not commit generated caches, virtual environments, build outputs, or local reports.

## Development

- Use `uv` for Python commands and dependency management.
- Target Python 3.12, matching `pyproject.toml`.
- Follow the existing `src/` layout and keep changes small and focused.
- Prefer updating existing modules and tests over introducing new abstractions.
- Update `README.md` and/or `CHANGELOG.md` when user-facing behavior, tools, configuration, or workflows change.

## Verification

Before committing relevant changes, run focused checks. For broad repository changes, use:

```bash
uv run ruff check
uv run pytest
```

For Python changes that affect typing-sensitive code, also run:

```bash
uv run ty check
```

## Security and Runtime Boundaries

- Never hardcode secrets, tokens, local machine paths, or credentials.
- Treat ChimeraX command execution as a boundary: validate inputs where practical and avoid exposing unsafe shell execution.
- Keep error messages useful without leaking sensitive local details.
