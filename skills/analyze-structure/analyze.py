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
import re
import sys
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
) -> Path:
    """Capture a screenshot and save to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if auto_fit:
        _try_command("view", base_url)
    _run_command(f"save {output_path} width {width} height {height}", base_url)
    return output_path


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
    """Parse ``info chains`` output into a list of chain dicts."""
    chains: list[dict[str, str]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("chain"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            chain_id = parts[0].split("/")[-1] if "/" in parts[0] else parts[0]
            chain_type = parts[1] if len(parts) > 1 else "unknown"
            chains.append({"id": chain_id, "type": chain_type})
    return chains


def _parse_selection_count(text: str) -> int:
    """Parse atom count from ``info sel`` or ``info atoms`` output."""
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
    """Parse ligand residue info from ``info residues ligand`` output."""
    ligands: list[dict[str, str | int]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Typical format: "/A MK1 902" or "#1/A:902 MK1"
        # Try common patterns
        m = re.search(r"[/#](\w)\s*[:/]?\s*(\w+)\s+(\d+)", line)
        if m:
            ligands.append(
                {
                    "chain": m.group(1),
                    "name": m.group(2),
                    "number": int(m.group(3)),
                }
            )
            continue
        # Alternative: "MK1 /B:902"
        m = re.search(r"(\w{2,4})\s+/(\w):(\d+)", line)
        if m:
            ligands.append(
                {
                    "name": m.group(1),
                    "chain": m.group(2),
                    "number": int(m.group(3)),
                }
            )
    return ligands


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


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

    # Protein
    _try_command("select protein", base_url)
    out = _try_command("info sel", base_url)
    if out and _parse_selection_count(out) > 0:
        result["has_protein"] = True
    _try_command("select clear", base_url)

    # Ligand
    _try_command("select ligand", base_url)
    out = _try_command("info sel", base_url)
    if out and _parse_selection_count(out) > 0:
        result["has_ligand"] = True
    _try_command("select clear", base_url)

    # Nucleic
    _try_command("select nucleic", base_url)
    out = _try_command("info sel", base_url)
    if out and _parse_selection_count(out) > 0:
        result["has_nucleic"] = True
    _try_command("select clear", base_url)

    # Ligand details
    if result["has_ligand"]:
        out = _try_command("info residues ligand", base_url)
        if out:
            result["ligands"] = _parse_ligand_residues(out)

    # Water count
    _try_command("select :HOH", base_url)
    out = _try_command("info sel", base_url)
    if out:
        result["water_count"] = _parse_residue_count(out)
    _try_command("select clear", base_url)

    # Multimer detection: 2+ chains of the same type
    type_counts: dict[str, int] = {}
    for chain in result["chains"]:
        t = chain.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    result["is_multimer"] = any(v >= 2 for v in type_counts.values())

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
    out = _try_command(f"align #1/{chain_a} to #1/{chain_b}", base_url)
    if out:
        rmsd = _parse_float(out, r"RMSD\s+(?:between\s+.+\s+is\s+|=\s*)([\d.]+)")
        ca_count = _parse_int(out, r"(\d+)\s+(?:atom|CA)")
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

    # Atom count for ligand
    _try_command("select ligand", base_url)
    out = _try_command("info sel", base_url)
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
    _try_command("select zone ligand 4 protein", base_url)
    _try_command("show sel atoms", base_url)
    _try_command("style sel stick", base_url)
    _try_command("color sel cornflowerblue", base_url)
    _try_command("color sel byhetero", base_url)
    _try_command("show ligand atoms", base_url)
    _try_command("style ligand stick", base_url)
    _try_command("color ligand magenta", base_url)
    _try_command("color ligand byhetero", base_url)
    _try_command("view ligand", base_url)

    # Count selected binding site atoms
    out = _try_command("info sel", base_url)
    if out:
        data["binding_site_atoms"] = _parse_selection_count(out)
    _try_command("select clear", base_url)

    fname = f"{img_num:02d}_binding_site.png"
    _take_screenshot(images_dir.joinpath(fname), base_url, width, height)
    screenshots.append(f"images/{fname}")
    img_num += 1

    # Hydrogen bonds
    _try_command("addh", base_url)
    out = _try_command("hbonds ligand restrict cross reveal true color cyan", base_url)
    if out:
        hbond_count = _parse_int(out, r"Found\s+(\d+)\s+hydrogen\s+bond")
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
        data["contact_count"] = _parse_int(out, r"(\d+)")
        data["contacts_raw"] = out.strip()

    # Clashes
    out = _try_command("clashes ligand restrict cross", base_url)
    if out:
        data["clash_count"] = _parse_int(out, r"(\d+)")
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
    img_num: int,
    base_url: str,
) -> tuple[dict, int]:
    """Compute buried surface area between first two chains."""
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
    out = _try_command(f"interfaces #1/{chain_a} contact #1/{chain_b}", base_url)
    if out:
        bsa = _parse_float(out, r"([\d,.]+)\s*(?:A\^2|angstrom)")
        data["chain_a"] = chain_a
        data["chain_b"] = chain_b
        data["buried_surface_area"] = bsa
        data["raw_output"] = out.strip()

    return {"status": "ok", "screenshots": [], "data": data}, img_num


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

    # Try to extract title and resolution from open output
    if open_out:
        # Title often in the open command output
        title_match = re.search(r"(?:title|name)\s*[=:]\s*(.+)", open_out, re.IGNORECASE)
        if title_match:
            structure["title"] = title_match.group(1).strip()
        res_match = re.search(r"resolution\s*[=:]\s*([\d.]+)", open_out, re.IGNORECASE)
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
            result, img_num = analyze_dimer_interface(detection["chains"], img_num, base_url)
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
