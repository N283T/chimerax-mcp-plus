#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28.0"]
# ///
"""Automated structural analysis of PDB structures via ChimeraX REST API.

Loads a structure, detects contents, runs analysis sections,
captures screenshots, and outputs a JSON summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

# ---------------------------------------------------------------------------
# REST client helpers
# ---------------------------------------------------------------------------

DEFAULT_PORT = 63269
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 768

_RESET_COMMANDS = [
    "hide pseudobonds",
    "hide atoms",
    "hide surface",
    "cartoon",
    "color byhetero",
    "lighting soft",
    "view",
]


def _run_command(command: str, base_url: str) -> str:
    """Execute a ChimeraX command and return the text output.

    Raises on HTTP errors.
    """
    encoded = quote(command, safe="")
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(f"{base_url}/run?command={encoded}")
        resp.raise_for_status()
        return resp.text


def _try_command(command: str, base_url: str) -> str | None:
    """Execute a command, returning None on any failure."""
    try:
        return _run_command(command, base_url)
    except Exception:
        return None


def _reset_display(base_url: str) -> None:
    """Reset ChimeraX to a clean default state."""
    for cmd in _RESET_COMMANDS:
        _try_command(cmd, base_url)


def _take_screenshot(
    output_path: Path,
    base_url: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    *,
    auto_fit: bool = False,
    fit_target: str | None = None,
    pad: float = 0.15,
) -> Path:
    """Capture a screenshot and save to *output_path*.

    Sets the ChimeraX window size to match the requested image dimensions
    before saving so that the aspect ratios are consistent and nothing
    gets cropped.

    *fit_target*: atom spec to focus on (e.g. "ligand"). If None and
    auto_fit is True, fits all models.
    *pad*: fraction of padding around the target (default 0.15).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fit_target:
        _try_command(f"view {fit_target} pad {pad}", base_url)
    elif auto_fit:
        _try_command(f"view pad {pad}", base_url)
    _run_command(
        f"save {output_path} width {width} height {height} supersample 3",
        base_url,
    )
    return output_path


def _build_tool_screenshot_script(
    tool_name: str,
    output_path: str,
    padding: int = 10,
) -> str:
    """Build a Python script for ChimeraX to capture a tool window.

    Captures the tool's ui_area, then auto-crops to the non-white content
    region and adds uniform padding.
    """
    lines = [
        "from Qt.QtCore import Qt",
        "from Qt.QtGui import QPixmap, QPainter, QColor, QImage",
        "from Qt.QtWidgets import QApplication",
        "",
        f"tool_name = {tool_name!r}",
        f"output_path = {output_path!r}",
        f"padding = {padding!r}",
        "",
        "target = None",
        "for t in session.tools.list():",
        "    if t.tool_name == tool_name:",
        "        target = t",
        "        break",
        "",
        "if target is None:",
        "    print('ERROR: Tool ' + repr(tool_name) + ' not found')",
        "else:",
        "    try:",
        "        ua = target.tool_window.ui_area",
        "        pixmap = ua.grab()",
        "        img = pixmap.toImage()",
        "        w, h = img.width(), img.height()",
        # Detect background from bottom-right corner pixel
        "        bg = img.pixel(w - 1, h - 1)",
        "        min_x, min_y, max_x, max_y = w, h, 0, 0",
        "        for y in range(h):",
        "            for x in range(w):",
        "                if img.pixel(x, y) != bg:",
        "                    min_x = min(min_x, x)",
        "                    min_y = min(min_y, y)",
        "                    max_x = max(max_x, x)",
        "                    max_y = max(max_y, y)",
        "        if max_x >= min_x and max_y >= min_y:",
        "            cropped = pixmap.copy(",
        "                min_x, min_y,",
        "                max_x - min_x + 1,",
        "                max_y - min_y + 1,",
        "            )",
        "        else:",
        "            cropped = pixmap",
        # Add padding
        "        if padding > 0:",
        "            cw = cropped.width() + 2 * padding",
        "            ch = cropped.height() + 2 * padding",
        "            padded = QPixmap(cw, ch)",
        "            padded.fill(QColor(255, 255, 255))",
        "            painter = QPainter(padded)",
        "            painter.drawPixmap(padding, padding, cropped)",
        "            painter.end()",
        "            cropped = padded",
        "        if not cropped.save(output_path):",
        "            print('ERROR: Failed to save to ' + repr(output_path))",
        "        else:",
        "            print('OK: ' + output_path)",
        "    except Exception as exc:",
        "        print('ERROR: ' + str(exc))",
    ]
    return "\n".join(lines)


def _take_tool_screenshot(
    tool_name: str,
    output_path: Path,
    base_url: str,
    padding: int = 10,
) -> bool:
    """Capture a ChimeraX tool window screenshot via runscript.

    Temporarily shrinks the window so the tool panel is compact,
    auto-crops whitespace, then restores the original window size.
    Returns True on success, False on failure.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Shrink window so tool panel is compact
    cur_size = _try_command("windowsize", base_url) or ""
    _try_command("windowsize 400 400", base_url)
    script = _build_tool_screenshot_script(tool_name, str(output_path), padding)
    fd, script_path = tempfile.mkstemp(suffix=".py", prefix="cx_tool_grab_")
    os.close(fd)
    try:
        Path(script_path).write_text(script)
        out = _try_command(f"runscript {script_path}", base_url)
        return bool(out and "OK:" in out)
    finally:
        Path(script_path).unlink(missing_ok=True)
        # Restore original window size
        m = re.search(r"window size (\d+) (\d+)", cur_size)
        if m:
            _try_command(f"windowsize {m.group(1)} {m.group(2)}", base_url)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_float(text: str, pattern: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def _parse_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _parse_chain_info(text: str) -> list[dict[str, str]]:
    """Parse ``info chains`` output into a list of chain dicts.

    ChimeraX format: ``chain id /A chain_id A``
    """
    chains: list[dict[str, str]] = []
    for line in text.strip().splitlines():
        # Match "chain id /X chain_id X"
        m = re.search(r"chain\s+id\s+/(\w)\s+chain_id\s+(\w)", line)
        if m:
            chains.append({"id": m.group(1)})
    return chains


def _parse_selection_count(text: str) -> int:
    """Parse atom count from ``info sel`` or ``select`` output.

    Handles: ``94 atoms, ...`` and ``Selected 214 atoms``.
    """
    # "Selected N atoms" from select commands
    m = re.search(r"[Ss]elected\s+(\d+)\s+atom", text)
    if m:
        return int(m.group(1))
    # "N atoms, N bonds, ..." from info commands
    m = re.search(r"(\d+)\s+atom", text)
    return int(m.group(1)) if m else 0


def _parse_residue_count(text: str) -> int:
    """Parse residue count from ``info`` output."""
    m = re.search(r"(\d+)\s+residue", text)
    return int(m.group(1)) if m else 0


def _parse_model_counts(text: str) -> dict[str, int]:
    """Parse atom/bond/residue counts from ``info models`` output."""
    atoms = _parse_int(text, r"(\d+)\s+atom") or 0
    bonds = _parse_int(text, r"(\d+)\s+bond") or 0
    residues = _parse_int(text, r"(\d+)\s+residue") or 0
    return {"atom_count": atoms, "bond_count": bonds, "residue_count": residues}


def _parse_ligand_residues(text: str) -> list[dict[str, str | int]]:
    """Parse ligand residue info from ``info residues ligand`` output.

    ChimeraX format: ``residue id /B:902 name MK1``
    """
    ligands: list[dict[str, str | int]] = []
    for line in text.strip().splitlines():
        # "residue id /B:902 name MK1"
        m = re.search(r"residue\s+id\s+/(\w):(\d+)\s+name\s+(\w+)", line)
        if m:
            ligands.append(
                {
                    "chain": m.group(1),
                    "number": int(m.group(2)),
                    "name": m.group(3),
                }
            )
    return ligands


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _select_count(spec: str, base_url: str) -> int:
    """Select atoms and return count. Uses combined command for reliability."""
    out = _try_command(f"select {spec}; info sel", base_url)
    _try_command("select clear", base_url)
    return _parse_selection_count(out) if out else 0


def detect_contents(base_url: str) -> dict:
    """Detect what the loaded structure contains."""
    result: dict = {
        "has_protein": False,
        "has_ligand": False,
        "has_nucleic": False,
        "is_multimer": False,
        "chains": [],
        "ligands": [],
        "water_count": 0,
    }

    # Chains
    out = _try_command("info chains #1", base_url)
    if out:
        result["chains"] = _parse_chain_info(out)

    # Content detection using combined select+info commands
    protein_count = _select_count("protein", base_url)
    result["has_protein"] = protein_count > 0

    ligand_count = _select_count("ligand", base_url)
    result["has_ligand"] = ligand_count > 0

    nucleic_count = _select_count("nucleic", base_url)
    result["has_nucleic"] = nucleic_count > 0

    # Ligand details
    if result["has_ligand"]:
        out = _try_command("info residues ligand", base_url)
        if out:
            result["ligands"] = _parse_ligand_residues(out)

    # Water count
    out = _try_command("select :HOH; info sel", base_url)
    if out:
        result["water_count"] = _parse_residue_count(out)
    _try_command("select clear", base_url)

    # Detect chain types and multimer
    # Test each chain for protein content
    protein_chains = 0
    for chain in result["chains"]:
        cid = chain["id"]
        count = _select_count(f"#1/{cid} & protein", base_url)
        chain["type"] = "protein" if count > 0 else "other"
        if count > 0:
            protein_chains += 1
    # Check nucleic chains
    for chain in result["chains"]:
        if chain["type"] == "other":
            cid = chain["id"]
            count = _select_count(f"#1/{cid} & nucleic", base_url)
            if count > 0:
                chain["type"] = "nucleic"

    result["is_multimer"] = protein_chains >= 2

    return result


# ---------------------------------------------------------------------------
# Analysis sections
# ---------------------------------------------------------------------------

# Each section returns a dict with:
#   status: "ok" | "skipped" | "error"
#   screenshots: list[str]  (relative paths)
#   data: dict  (section-specific data)


def analyze_overview(
    pdb_id: str,
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Capture overview screenshot and collect basic metadata."""
    screenshots: list[str] = []
    data: dict = {}

    _reset_display(base_url)
    _try_command("color bychain", base_url)

    fname = f"{img_num:02d}_overview.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height, auto_fit=True)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Metadata
    out = _try_command("info #1", base_url)
    if out:
        data["raw_info"] = out.strip()

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_secondary_structure(
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Run DSSP and capture secondary structure view."""
    screenshots: list[str] = []
    data: dict = {}

    _reset_display(base_url)
    out = _try_command("dssp #1", base_url)
    if out is None:
        return {"status": "error", "screenshots": [], "data": {"error": "dssp failed"}}, img_num

    _try_command("cartoon style arrowheads true", base_url)
    _try_command("color bychain", base_url)

    fname = f"{img_num:02d}_secondary_structure.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height, auto_fit=True)
    screenshots.append(f"images/{fname}")
    img_num += 1

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_chain_alignment(
    chains: list[dict[str, str]],
    img_num: int,
    base_url: str,
) -> tuple[dict, int]:
    """Align two chains and report RMSD."""
    data: dict = {}

    # Find first two chains of the same type
    type_chains: dict[str, list[str]] = {}
    for c in chains:
        t = c.get("type", "unknown")
        cid = c.get("id", "")
        type_chains.setdefault(t, []).append(cid)

    pair = None
    for chain_ids in type_chains.values():
        if len(chain_ids) >= 2:
            pair = (chain_ids[0], chain_ids[1])
            break

    if pair is None:
        return {"status": "skipped", "screenshots": [], "data": {}}, img_num

    chain_a, chain_b = pair
    # Use @CA for reliable alignment of protein chains
    out = _try_command(f"align #1/{chain_a}@CA to #1/{chain_b}@CA", base_url)
    if out:
        # "RMSD between 99 atom pairs is 0.400 angstroms"
        rmsd = _parse_float(out, r"RMSD\s+between\s+\d+\s+atom\s+pairs\s+is\s+([\d.]+)")
        ca_count = _parse_int(out, r"(\d+)\s+atom\s+pair")
        data["chain_a"] = chain_a
        data["chain_b"] = chain_b
        data["rmsd"] = rmsd
        data["ca_atoms"] = ca_count
        data["raw_output"] = out.strip()
    else:
        data["error"] = "align command failed"

    return {"status": "ok", "screenshots": [], "data": data}, img_num


def analyze_ligand_overview(
    ligands: list[dict],
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Show ligand as sticks and capture screenshot."""
    screenshots: list[str] = []
    data: dict = {"ligands": ligands}

    _reset_display(base_url)
    _try_command("show ligand atoms", base_url)
    _try_command("style ligand stick", base_url)
    _try_command("color ligand magenta", base_url)
    _try_command("color ligand byhetero", base_url)
    _try_command("view ligand", base_url)

    fname = f"{img_num:02d}_ligand_overview.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Atom count for ligand (combined command for reliability)
    out = _try_command("select ligand; info sel", base_url)
    if out:
        data["ligand_atom_count"] = _parse_selection_count(out)
    _try_command("select clear", base_url)

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_binding_site(
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Analyze binding site: residues, H-bonds, contacts, clashes."""
    screenshots: list[str] = []
    data: dict = {}

    # Binding site residues
    _reset_display(base_url)
    # select zone returns "Selected N atoms" — capture it directly
    out = _try_command("select zone ligand 4 protein", base_url)
    if out:
        data["binding_site_atoms"] = _parse_selection_count(out)
    _try_command("show sel atoms", base_url)
    _try_command("style sel stick", base_url)
    _try_command("color sel cornflowerblue", base_url)
    _try_command("color sel byhetero", base_url)
    _try_command("show ligand atoms", base_url)
    _try_command("style ligand stick", base_url)
    _try_command("color ligand magenta", base_url)
    _try_command("color ligand byhetero", base_url)
    _try_command("view ligand", base_url)
    _try_command("select clear", base_url)

    fname = f"{img_num:02d}_binding_site.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Hydrogen bonds
    _try_command("addh", base_url)
    out = _try_command("hbonds ligand restrict cross reveal true color cyan", base_url)
    if out:
        # Matches: "Found N hydrogen bonds", "N hydrogen bonds found", "N H-bonds"
        hbond_count = _parse_int(out, r"(\d+)\s+hydrogen\s+bond")
        if hbond_count is None:
            hbond_count = _parse_int(out, r"(\d+)\s+H-bond")
        data["hbond_count"] = hbond_count
        data["hbonds_raw"] = out.strip()

    fname = f"{img_num:02d}_hbonds.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Contacts
    out = _try_command("contacts ligand restrict cross", base_url)
    if out:
        data["contact_count"] = _parse_int(out, r"(\d+)\s+contact")
        data["contacts_raw"] = out.strip()

    # Clashes
    out = _try_command("clashes ligand restrict cross", base_url)
    if out:
        clash_count = _parse_int(out, r"(\d+)\s+clash")
        data["clash_count"] = clash_count if clash_count is not None else 0
        data["clashes_raw"] = out.strip()

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_surface(
    has_ligand: bool,
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Molecular surface + coulombic electrostatic surface."""
    screenshots: list[str] = []
    data: dict = {}

    # Molecular surface
    _reset_display(base_url)
    _try_command("surface protein", base_url)

    if has_ligand:
        _try_command("transparency 70 target s", base_url)
        _try_command("show ligand atoms", base_url)
        _try_command("style ligand sphere", base_url)
        _try_command("color ligand magenta", base_url)
        fname = f"{img_num:02d}_surface_ligand.png"
    else:
        _try_command("color bychain", base_url)
        fname = f"{img_num:02d}_surface.png"

    _take_screenshot(images_dir.joinpath(fname), base_url, width, height, auto_fit=True)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Coulombic
    out = _try_command("coulombic surfaces #1", base_url)
    if out is None:
        # Try with addh first
        _try_command("addh", base_url)
        out = _try_command("coulombic surfaces #1", base_url)

    fname = f"{img_num:02d}_coulombic.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height, auto_fit=True)
    screenshots.append(f"images/{fname}")
    img_num += 1

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_dimer_interface(
    chains: list[dict[str, str]],
    images_dir: Path,
    img_num: int,
    base_url: str,
) -> tuple[dict, int]:
    """Compute buried surface area between first two chains."""
    screenshots: list[str] = []
    data: dict = {}

    type_chains: dict[str, list[str]] = {}
    for c in chains:
        t = c.get("type", "unknown")
        cid = c.get("id", "")
        type_chains.setdefault(t, []).append(cid)

    pair = None
    for chain_ids in type_chains.values():
        if len(chain_ids) >= 2:
            pair = (chain_ids[0], chain_ids[1])
            break

    if pair is None:
        return {"status": "skipped", "screenshots": [], "data": {}}, img_num

    chain_a, chain_b = pair
    # "interfaces #1" computes all chain interfaces
    # Output: "1 buried areas: B A 2326"
    out = _try_command("interfaces #1", base_url)
    if out:
        # Parse buried area value from "B A 2326" pattern
        bsa = _parse_float(out, r"buried\s+areas?:.+?(\d+)\s*$")
        if bsa is None:
            # Try any number at end of line after chain IDs
            bsa = _parse_float(out, r"\b([0-9]+(?:\.[0-9]+)?)\s*$")
        data["chain_a"] = chain_a
        data["chain_b"] = chain_b
        data["buried_surface_area"] = bsa
        data["raw_output"] = out.strip()

    # Capture "Chain Contacts" tool panel screenshot
    fname = f"{img_num:02d}_chain_contacts.png"
    ok = _take_tool_screenshot("Chain Contacts", images_dir.joinpath(fname), base_url)
    if ok:
        screenshots.append(f"images/{fname}")
        img_num += 1

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


def analyze_bfactors(
    images_dir: Path,
    img_num: int,
    base_url: str,
    width: int,
    height: int,
) -> tuple[dict, int]:
    """Color by B-factor and capture screenshot."""
    screenshots: list[str] = []
    data: dict = {}

    _reset_display(base_url)
    _try_command("color bfactor", base_url)

    fname = f"{img_num:02d}_bfactor.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height, auto_fit=True)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Parse B-factor range
    out = _try_command("info atoms #1 attr bfactor", base_url)
    if out:
        values = re.findall(r"bfactor\s*=?\s*([\d.]+)", out)
        if values:
            floats = [float(v) for v in values]
            data["bfactor_min"] = min(floats)
            data["bfactor_max"] = max(floats)
        data["bfactors_raw"] = out.strip()[:500]  # truncate to avoid huge output

    return {"status": "ok", "screenshots": screenshots, "data": data}, img_num


# ---------------------------------------------------------------------------
# Orchestrator helpers
# ---------------------------------------------------------------------------

_SKIPPED: dict = {"status": "skipped", "screenshots": [], "data": {}}


def _error_result(error: str) -> dict:
    return {"status": "error", "screenshots": [], "data": {"error": error}}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_analysis(
    pdb_id: str,
    output_dir: Path,
    base_url: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> dict:
    """Run full structural analysis and return JSON-serializable result."""
    images_dir = output_dir.joinpath("images")
    images_dir.mkdir(parents=True, exist_ok=True)

    # Match window aspect ratio to output image to prevent cropping
    _try_command(f"windowsize {width} {height}", base_url)

    errors: list[dict[str, str]] = []
    sections: dict[str, dict] = {}
    img_num = 1

    # Close existing models and open structure
    _try_command("close all", base_url)
    print(f"Opening {pdb_id}...")
    open_out = _run_command(f"open {pdb_id}", base_url)

    # Get model info
    model_info_out = _try_command("info #1", base_url) or ""
    counts = _parse_model_counts(model_info_out)

    # Detect contents
    print("Detecting structure contents...")
    detection = detect_contents(base_url)

    # Metadata
    structure: dict = {
        "title": "",
        "resolution": "",
        **counts,
        "chains": detection["chains"],
    }

    # Parse title from open output: "title:  \n**...**"
    if open_out:
        # Extract text between ** markers (bold title in markdown output)
        title_match = re.search(r"\*\*(.+?)\*\*", open_out, re.DOTALL)
        if title_match:
            # Clean up: remove newlines, collapse spaces
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            structure["title"] = title
        # Extract resolution from title text (e.g., "1.9 angstroms")
        res_match = re.search(r"([\d.]+)\s*(?:angstroms?|A)\s+resolution", open_out, re.IGNORECASE)
        if res_match:
            structure["resolution"] = res_match.group(1)
        else:
            # Try "resolution X.X" pattern
            res_match = re.search(r"resolution\s+([\d.]+)", open_out, re.IGNORECASE)
            if res_match:
                structure["resolution"] = res_match.group(1)

    # -- Section: Overview --
    print("Section: Overview...")
    try:
        result, img_num = analyze_overview(pdb_id, images_dir, img_num, base_url, width, height)
        sections["overview"] = result
    except Exception as e:
        errors.append({"section": "overview", "command": "", "error": str(e)})
        sections["overview"] = _error_result(str(e))

    # -- Section: Secondary Structure --
    if detection["has_protein"]:
        print("Section: Secondary Structure...")
        try:
            result, img_num = analyze_secondary_structure(
                images_dir, img_num, base_url, width, height
            )
            sections["secondary_structure"] = result
        except Exception as e:
            errors.append({"section": "secondary_structure", "command": "", "error": str(e)})
            sections["secondary_structure"] = _error_result(str(e))
    else:
        sections["secondary_structure"] = _SKIPPED

    # -- Section: Chain Alignment --
    if detection["is_multimer"]:
        print("Section: Chain Alignment...")
        try:
            result, img_num = analyze_chain_alignment(detection["chains"], img_num, base_url)
            sections["chain_alignment"] = result
        except Exception as e:
            errors.append({"section": "chain_alignment", "command": "", "error": str(e)})
            sections["chain_alignment"] = _error_result(str(e))
    else:
        sections["chain_alignment"] = _SKIPPED

    # -- Section: Ligand Overview --
    if detection["has_ligand"]:
        print("Section: Ligand Overview...")
        try:
            result, img_num = analyze_ligand_overview(
                detection["ligands"], images_dir, img_num, base_url, width, height
            )
            sections["ligand_overview"] = result
        except Exception as e:
            errors.append({"section": "ligand_overview", "command": "", "error": str(e)})
            sections["ligand_overview"] = _error_result(str(e))
    else:
        sections["ligand_overview"] = _SKIPPED

    # -- Section: Binding Site --
    if detection["has_ligand"]:
        print("Section: Binding Site...")
        try:
            result, img_num = analyze_binding_site(images_dir, img_num, base_url, width, height)
            sections["binding_site"] = result
        except Exception as e:
            errors.append({"section": "binding_site", "command": "", "error": str(e)})
            sections["binding_site"] = _error_result(str(e))
    else:
        sections["binding_site"] = _SKIPPED

    # -- Section: Surface --
    if detection["has_protein"]:
        print("Section: Surface...")
        try:
            result, img_num = analyze_surface(
                detection["has_ligand"], images_dir, img_num, base_url, width, height
            )
            sections["surface"] = result
        except Exception as e:
            errors.append({"section": "surface", "command": "", "error": str(e)})
            sections["surface"] = _error_result(str(e))
    else:
        sections["surface"] = _SKIPPED

    # -- Section: Dimer Interface --
    if detection["is_multimer"]:
        print("Section: Dimer Interface...")
        try:
            result, img_num = analyze_dimer_interface(
                detection["chains"], images_dir, img_num, base_url
            )
            sections["dimer_interface"] = result
        except Exception as e:
            errors.append({"section": "dimer_interface", "command": "", "error": str(e)})
            sections["dimer_interface"] = _error_result(str(e))
    else:
        sections["dimer_interface"] = _SKIPPED

    # -- Section: B-factors --
    print("Section: B-factors...")
    try:
        result, img_num = analyze_bfactors(images_dir, img_num, base_url, width, height)
        sections["bfactors"] = result
    except Exception as e:
        errors.append({"section": "bfactors", "command": "", "error": str(e)})
        sections["bfactors"] = _error_result(str(e))

    # Assemble output
    output = {
        "metadata": {
            "pdb_id": pdb_id.upper(),
            "analysis_date": datetime.now(UTC).isoformat(),
            "output_dir": str(output_dir),
        },
        "structure": structure,
        "detection": {
            "has_protein": detection["has_protein"],
            "has_ligand": detection["has_ligand"],
            "has_nucleic": detection["has_nucleic"],
            "is_multimer": detection["is_multimer"],
            "ligands": detection["ligands"],
            "water_count": detection["water_count"],
        },
        "sections": sections,
        "errors": errors,
    }

    # Write JSON
    json_path = output_dir.joinpath("analysis.json")
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"Analysis written to {json_path}")

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated structural analysis via ChimeraX REST API",
    )
    parser.add_argument("pdb_id", help="PDB ID or file path to analyze")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: reports/<id>-analysis)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="ChimeraX REST port")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Screenshot width")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Screenshot height")

    args = parser.parse_args()

    pdb_id = args.pdb_id
    output_dir = args.output_dir or Path(f"reports/{pdb_id.lower()}-analysis")
    base_url = f"http://127.0.0.1:{args.port}"

    # Verify ChimeraX is running
    try:
        _run_command("version", base_url)
    except Exception:
        print(f"ERROR: Cannot connect to ChimeraX at {base_url}", file=sys.stderr)
        print("Start ChimeraX with REST API enabled first.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {pdb_id} -> {output_dir}")
    result = run_analysis(pdb_id, output_dir, base_url, args.width, args.height)

    error_count = len(result["errors"])
    section_count = sum(1 for s in result["sections"].values() if s["status"] == "ok")
    total = len(result["sections"])
    print(f"Done: {section_count}/{total} sections completed, {error_count} errors")


if __name__ == "__main__":
    main()
