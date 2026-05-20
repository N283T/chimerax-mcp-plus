"""Helpers for bounded live ChimeraX Python API introspection."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx

from chimerax_mcp.commands import quote_chimerax_path

MARKER = "CHIMERAX_MCP_PYTHON_API_JSON="
_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_INVALID_SYMBOL_MESSAGE = (
    "symbol must be a dotted import path such as chimerax.atomic.AtomicStructure"
)
_DUNDER_MESSAGE = "symbol must not contain dunder segments"


def validate_symbol(symbol: str) -> str | None:
    """Validate a conservative dotted Python import path."""
    if not _SYMBOL_RE.fullmatch(symbol):
        return _INVALID_SYMBOL_MESSAGE
    if any(segment.startswith("__") and segment.endswith("__") for segment in symbol.split(".")):
        return _DUNDER_MESSAGE
    return None


def build_python_inspect_script(
    symbol: str,
    include_dir: bool,
    max_doc_chars: int,
) -> str:
    """Build a ChimeraX Python script that introspects one Python API symbol."""
    bounded_doc_chars = min(max(max_doc_chars, 1), 20_000)
    return f"""import importlib
import inspect
import json

marker = {MARKER!r}
symbol = {symbol!r}
include_dir = {include_dir!r}
max_doc_chars = {bounded_doc_chars}


def resolve_symbol(path):
    parts = path.split('.')
    last_error = None
    for end in range(len(parts), 0, -1):
        module_name = '.'.join(parts[:end])
        attrs = parts[end:]
        try:
            obj = importlib.import_module(module_name)
        except Exception as err:
            last_error = err
            continue
        try:
            for attr in attrs:
                obj = getattr(obj, attr)
            return obj
        except Exception as err:
            last_error = err
            break
    raise ImportError(f"{{path}} could not be resolved: {{last_error}}")


def safe_signature(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return None


def emit(payload):
    session.logger.info(marker + json.dumps(payload, sort_keys=True))


try:
    target = resolve_symbol(symbol)
    doc = inspect.getdoc(target) or ''
    payload = {{
        'status': 'ok',
        'symbol': symbol,
        'type': type(target).__name__,
        'module': getattr(target, '__module__', None),
        'signature': safe_signature(target),
        'doc': doc[:max_doc_chars],
    }}
    if include_dir:
        attributes = [name for name in dir(target) if not name.startswith('__')]
        payload['attributes'] = attributes[:100]
        payload['attributes_truncated'] = len(attributes) > 100
    emit(payload)
except Exception as err:
    emit({{
        'status': 'error',
        'symbol': symbol,
        'message': str(err),
        'error_type': type(err).__name__,
    }})
"""


def build_python_dir_script(symbol: str, filter_text: str | None, limit: int) -> str:
    """Build a ChimeraX Python script that lists public-ish attrs for a symbol."""
    bounded_limit = min(max(limit, 1), 1_000)
    return f"""import importlib
import json

marker = {MARKER!r}
symbol = {symbol!r}
filter_text = {filter_text!r}
limit = {bounded_limit}


def resolve_symbol(path):
    parts = path.split('.')
    last_error = None
    for end in range(len(parts), 0, -1):
        module_name = '.'.join(parts[:end])
        attrs = parts[end:]
        try:
            obj = importlib.import_module(module_name)
        except Exception as err:
            last_error = err
            continue
        try:
            for attr in attrs:
                obj = getattr(obj, attr)
            return obj
        except Exception as err:
            last_error = err
            break
    raise ImportError(f"{{path}} could not be resolved: {{last_error}}")


def emit(payload):
    session.logger.info(marker + json.dumps(payload, sort_keys=True))


try:
    target = resolve_symbol(symbol)
    attrs = [name for name in dir(target) if not name.startswith('__')]
    if filter_text:
        lowered = filter_text.lower()
        attrs = [name for name in attrs if lowered in name.lower()]
    emit({{
        'status': 'ok',
        'symbol': symbol,
        'attributes': attrs[:limit],
        'truncated': len(attrs) > limit,
        'count': len(attrs),
    }})
except Exception as err:
    emit({{
        'status': 'error',
        'symbol': symbol,
        'message': str(err),
        'error_type': type(err).__name__,
    }})
"""


def parse_introspection_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract an introspection JSON payload from ChimeraX command output."""
    log_messages = result.get("log_messages", {})
    if isinstance(log_messages, dict):
        for level in ("info", "note", "warning", "error"):
            messages = log_messages.get(level, [])
            if not isinstance(messages, list):
                continue
            for message in messages:
                if isinstance(message, str) and message.startswith(MARKER):
                    try:
                        payload = json.loads(message.removeprefix(MARKER))
                    except json.JSONDecodeError as err:
                        return {
                            "status": "error",
                            "message": f"Invalid introspection JSON payload: {err}",
                        }
                    if isinstance(payload, dict):
                        return payload
                    return {
                        "status": "error",
                        "message": "Introspection JSON payload was not an object",
                    }
    return {
        "status": "error",
        "message": "No introspection JSON payload found in ChimeraX output",
    }


def run_python_api_script(client: Any, script: str) -> dict[str, Any]:
    """Write, run, and parse a ChimeraX Python introspection script."""
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".py",
            prefix="chimerax_mcp_python_api_",
            delete=False,
        ) as temp_file:
            temp_file.write(script)
            temp_path = Path(temp_file.name)

        result = client.run_command(f"runscript {quote_chimerax_path(temp_path)}")
    except httpx.HTTPError as err:
        return {
            "status": "error",
            "message": f"HTTP error running ChimeraX command: {err}",
            "error_type": type(err).__name__,
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    chimerax_error = result.get("error")
    if isinstance(chimerax_error, dict):
        return {
            "status": "error",
            "message": str(chimerax_error.get("message", "ChimeraX command failed")),
            "error_type": str(chimerax_error.get("type", "ChimeraXError")),
            "error": chimerax_error,
        }
    if chimerax_error:
        return {
            "status": "error",
            "message": str(chimerax_error),
            "error_type": "ChimeraXError",
            "error": chimerax_error,
        }
    return parse_introspection_result(result)
