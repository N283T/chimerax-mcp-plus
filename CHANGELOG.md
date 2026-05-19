# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `chimerax_rich_log()` to write trusted HTML directly to the ChimeraX Log.
- `chimerax_rich_report()` as a themed block composer for dashboard-like ChimeraX Log output.
- Claude Code agents for specialized ChimeraX workflows:
  - `chimerax-operator`: MCP operator for visualization and manipulation
  - `structural-biologist`: Structural biology analysis expert
  - `chimerax-developer`: Bundle/extension development with echidna

### Changed
- Made `chimerax_rich_report(theme="auto")` follow light/dark appearance via CSS color-scheme media queries.
- Removed private rich-log success sentinels from the visible ChimeraX Log output.
- Reworked `chimerax_rich_report()` into a themed block composer for dashboard-like ChimeraX Log output.
- Increased default `wait_seconds` from 10 to 15 for ChimeraX startup
- Added 3-second initial sleep before polling REST API (ChimeraX needs time to launch)
- Improved timeout message to indicate process may still be starting

### Added
- `background` parameter in `chimerax_start` to launch without waiting
- `chimerax_list_screenshots()` to list all saved screenshots
- `chimerax_cleanup_screenshots(older_than_days)` to delete old screenshots
- Better handling for slow startup scenarios

## [0.1.0] - 2025-02-25

### Added
- Initial release of chimerax-mcp-plus
- MCP server for UCSF ChimeraX molecular visualization
- REST API communication with ChimeraX
- Screenshot capture for 3D view and tool windows
- Session save/load support
- Model management commands

### Fixed
- Extended startup timeout from 5s to 10s for reliable ChimeraX launch
- Prevented duplicate ChimeraX process launches
- Enabled `log true` for GUI log display alongside JSON API
- Fixed log message extraction to include 'note' level messages
