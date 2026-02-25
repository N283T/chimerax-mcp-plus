# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
