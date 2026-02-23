---
name: analyze-structure
description: Comprehensive structural analysis with report generation
allowed-tools: Read, Write, Bash, Glob, Grep
timeout: 300000
---

# Analyze Structure

Automated structural analysis that loads a PDB structure via ChimeraX, runs analyses, captures screenshots, and compiles a Markdown report.

## Usage

```
/analyze-structure <PDB_ID_or_filepath>
```

## Prerequisites

- UCSF ChimeraX running with REST API enabled
- `uv` available in PATH

## Workflow

### Phase 1: Ensure ChimeraX Running

Use MCP tools to verify ChimeraX is available:

1. `chimerax_status()` — if not running, call `chimerax_start()`

### Phase 2: Run Analysis Script

```bash
uv run ${SKILL_ROOT}/analyze.py <ID> --output-dir reports/<id>-analysis
```

The script handles: structure loading, content detection, all analysis sections, screenshots, and outputs `analysis.json`.

### Phase 3: Write Report

1. Read `reports/<id>-analysis/analysis.json`
2. Write `reports/<id>-analysis/report.md` using the template and data below

## Report Template

Use the JSON fields to populate this template. **Number sections sequentially** — skip irrelevant sections (where `status` is `"skipped"`) but don't leave numbering gaps.

```markdown
# Structural Analysis of <structure.title> (PDB: <metadata.pdb_id>)

## 1. Overview

| Property | Value |
|----------|-------|
| PDB ID | <metadata.pdb_id> |
| Title | <structure.title> |
| Resolution | <structure.resolution> A |
| Chains | <structure.chains — list ids and types> |
| Total Atoms | <structure.atom_count> |
| Total Bonds | <structure.bond_count> |
| Total Residues | <structure.residue_count> |
| Ligand | <detection.ligands[0].name> (<chain> residue <number>) |
| Water Molecules | <detection.water_count> |

<Interpretation>

![Overall structure](<sections.overview.screenshots[0]>)
*Figure N: Overall structure colored by chain.*

## N. Secondary Structure  (if sections.secondary_structure.status == "ok")
<Interpretation of fold and key features>
![Secondary structure](<screenshot path>)

## N. Chain Symmetry Analysis  (if sections.chain_alignment.status == "ok")
| Metric | Value |
|--------|-------|
| CA atoms | <data.ca_atoms> |
| RMSD | <data.rmsd> A |
<Interpretation>

## N. Ligand: <NAME>  (if sections.ligand_overview.status == "ok")
<Table + interpretation>
![Ligand](<screenshot path>)

## N. Binding Site Analysis  (if sections.binding_site.status == "ok")
### N.1 Binding Site Residues
![Binding site](<screenshot path>)
### N.2 Hydrogen Bonds
| Metric | Value |
|--------|-------|
| H-bonds (ligand-protein) | <data.hbond_count> |
![H-bonds](<screenshot path>)
### N.3 Contacts and Clashes
| Analysis | Count |
|----------|-------|
| Contacts | <data.contact_count> |
| Clashes | <data.clash_count> |

## N. Molecular Surface Analysis  (if sections.surface.status == "ok")
### N.1 Molecular Surface
![Surface](<screenshot path>)
### N.2 Electrostatic Surface Potential
![Coulombic](<screenshot path>)

## N. Dimer Interface  (if sections.dimer_interface.status == "ok")
| Property | Value |
|----------|-------|
| Buried Surface Area | <data.buried_surface_area> A^2 |
<Interpretation>

## N. Temperature Factors (B-factors)  (always — sections.bfactors)
| Property | Value |
|----------|-------|
| B-factor range | <data.bfactor_min> - <data.bfactor_max> A^2 |
![B-factors](<screenshot path>)

## N. Summary
| Analysis | Key Finding |
|----------|-------------|
| Structure | <one-line> |
| Ligand Fit | <if applicable> |
| H-bond Network | <if applicable> |
| Chain RMSD | <if applicable> |
| Interface | <if applicable> |
| Flexibility | <B-factor observation> |
| Electrostatics | <surface observation> |

---
*Generated using UCSF ChimeraX via chimerax-mcp-plus MCP server*
*Analysis date: <metadata.analysis_date>*
```

## Interpretation Guidelines

For each section, write 1-3 sentences of scientific interpretation:

- **Overview**: What is this structure? Biological significance?
- **Secondary Structure**: Fold type? Key structural features?
- **Chain Alignment**: How similar are chains? What does RMSD indicate?
- **Ligand**: What is it? Mechanism of action?
- **Binding Site**: Contact quality? 0 clashes = excellent fit
- **Surface**: Is ligand buried or exposed? Electrostatic complementarity?
- **Interface**: How extensive? Biologically relevant?
- **B-factors**: Flexible/rigid regions? Functional implications?

For any section with `status: "error"`, add a note: *"Note: [analysis] could not be completed."*

## Related

- **Skill**: `/explore-chimerax-commands` — Command reference
- **Skill**: `/explore-chimerax` — General ChimeraX documentation
