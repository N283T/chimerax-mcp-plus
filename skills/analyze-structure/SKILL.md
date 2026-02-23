---
name: analyze-structure
description: Comprehensive structural analysis with report generation
allowed-tools: Read, Write, Bash, Glob, Grep
timeout: 300000
---

# Analyze Structure

Automated structural analysis workflow that loads a PDB structure, detects its contents, runs relevant analyses, captures screenshots, and compiles a Markdown report.

## Usage

```
/analyze-structure <PDB_ID_or_filepath>
```

Examples:
```
/analyze-structure 1HSG
/analyze-structure 1UBQ
/analyze-structure /path/to/structure.pdb
```

## Prerequisites

- UCSF ChimeraX installed locally
- ChimeraX MCP server (`chimerax-mcp-plus`) configured in Claude Code MCP settings
- Write access to the working directory for `reports/` output

## Workflow

Follow each phase sequentially. If any individual command fails, note the failure in the report and continue to the next step. **Never abort the entire workflow for a single command failure.**

### Phase 0: Setup

1. Parse the argument as `ID` (PDB ID or file path). Uppercase PDB IDs for display.
2. Set variables:
   - `REPORT_DIR` = `reports/<id>-analysis` (lowercase id for directory)
   - `IMAGES_DIR` = `reports/<id>-analysis/images`
3. Create directories:
   ```bash
   mkdir -p <IMAGES_DIR>
   ```
4. Ensure ChimeraX is running:
   - Call `chimerax_status()` — if not running, call `chimerax_start()`
5. Close any existing models:
   - Call `chimerax_close(model_spec="all")`

### Phase 1: Load & Detect

1. **Open structure**: `chimerax_open(path_or_id="<ID>")`
2. **Get model info**: `chimerax_models()` — record atom count, bond count, residue count
3. **Detect contents** via `chimerax_run()`:

   ```
   info chains #1           → parse chain IDs and types
   select protein; info sel  → HAS_PROTEIN (true if atoms selected)
   select ligand; info sel   → HAS_LIGAND (true if atoms selected)
   select nucleic; info sel  → HAS_NUCLEIC (true if atoms selected)
   ```

4. **If HAS_LIGAND**, identify the ligand:
   ```
   info residues ligand     → parse residue name, chain, number
   ```

5. **Detect multi-chain**: If 2+ chains of the same type (e.g., two protein chains) → `IS_MULTIMER = true`

6. **Retrieve structure metadata**:
   ```
   info #1 attr pdb_id
   info #1 attr title (or name)
   info #1 attr resolution
   ```
   These may not all be available — record what you can.

7. **Set section flags**:

   | Flag | Condition | Sections Enabled |
   |------|-----------|------------------|
   | `HAS_PROTEIN` | Protein detected | Secondary Structure, Surface, Coulombic |
   | `HAS_LIGAND` | Ligand detected | Ligand Overview, Binding Site, H-bonds, Contacts/Clashes |
   | `IS_MULTIMER` | 2+ chains same type | Chain Alignment, Interface |
   | `HAS_NUCLEIC` | Nucleic acid detected | (Skip DSSP; still do Surface, B-factors) |

### Phase 2: Analysis Sections

Run each applicable section. Track a screenshot counter (`IMG_NUM`, starting at 1) for sequential file naming: `01_overview.png`, `02_secondary_structure.png`, etc.

Each section follows the pattern:
1. Set up the visualization (reset, color, style)
2. Capture screenshot(s)
3. Record data for the report

---

#### Section: Overview (always)

1. `chimerax_reset()`
2. `chimerax_run("color bychain")`
3. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_overview.png", auto_fit=true)`
4. Record: PDB ID, title, resolution, chains, atom/residue/bond counts, ligand identity, water count

---

#### Section: Secondary Structure (if HAS_PROTEIN)

> Skip this section if the structure contains only nucleic acids (no protein).

1. `chimerax_reset()`
2. `chimerax_run("dssp #1")`
3. `chimerax_run("cartoon style arrowheads true")`
4. `chimerax_run("color bychain")`
5. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_secondary_structure.png", auto_fit=true)`
6. Note key structural features if identifiable from the structure

---

#### Section: Chain Alignment (if IS_MULTIMER)

1. Identify chains to align (e.g., chain A and chain B)
2. `chimerax_run("align #1/<A> to #1/<B>")` — parse RMSD from output
3. Record: number of CA atoms, RMSD value
4. Screenshot of superposition (optional — overview already shows both chains)

---

#### Section: Ligand Overview (if HAS_LIGAND)

1. `chimerax_reset()`
2. Show ligand as sticks with distinct color:
   ```
   chimerax_run("show ligand atoms")
   chimerax_run("style ligand stick")
   chimerax_run("color ligand magenta")       # base color (carbons)
   chimerax_run("color ligand byhetero")      # overrides N, O, S by element
   ```
3. `chimerax_view(target="ligand")`
4. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_ligand_overview.png")`
5. Record: residue name, chain, residue number, atom count

---

#### Section: Binding Site (if HAS_LIGAND)

**5.1 Binding Site Residues:**

1. `chimerax_reset()`
2. Show binding site:
   ```
   chimerax_run("select zone ligand 4 protein")
   chimerax_run("show sel atoms")
   chimerax_run("style sel stick")
   chimerax_run("color sel cornflowerblue")
   chimerax_run("color sel byhetero")
   chimerax_run("show ligand atoms")
   chimerax_run("style ligand stick")
   chimerax_run("color ligand magenta")       # base color (carbons)
   chimerax_run("color ligand byhetero")      # overrides N, O, S by element
   ```
3. `chimerax_view(target="ligand")`
4. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_binding_site.png")`
5. Record number of selected atoms

**5.2 Hydrogen Bonds:**

1. Add hydrogens and find H-bonds:
   ```
   chimerax_run("addh")
   chimerax_run("hbonds ligand restrict cross reveal true color cyan")
   ```
2. Parse H-bond count from output
3. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_hbonds.png")`

**5.3 Contacts and Clashes:**

1. `chimerax_run("contacts ligand restrict cross")` — parse contact count
2. `chimerax_run("clashes ligand restrict cross")` — parse clash count
3. Record both counts

---

#### Section: Molecular Surface (if HAS_PROTEIN)

**Molecular Surface:**

1. `chimerax_reset()`
2. If HAS_LIGAND:
   ```
   chimerax_run("surface protein")
   chimerax_run("transparency 70 target s")
   chimerax_run("show ligand atoms")
   chimerax_run("style ligand sphere")
   chimerax_run("color ligand magenta")
   ```
   Screenshot: `<IMAGES_DIR>/<NN>_surface_ligand.png`
3. If no ligand:
   ```
   chimerax_run("surface protein")
   chimerax_run("color bychain")
   ```
   Screenshot: `<IMAGES_DIR>/<NN>_surface.png`
4. `chimerax_screenshot(output_path=<chosen path>, auto_fit=true)`

**Coulombic Electrostatic Surface:**

1. `chimerax_run("coulombic surfaces #1")`
2. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_coulombic.png", auto_fit=true)`

---

#### Section: Dimer Interface (if IS_MULTIMER)

1. `chimerax_run("interfaces #1/<A> contact #1/<B>")` — parse buried surface area
2. Record: buried surface area value

---

#### Section: B-factors (always)

1. `chimerax_reset()`
2. `chimerax_run("color bfactor")`
3. `chimerax_screenshot(output_path="<IMAGES_DIR>/<NN>_bfactor.png", auto_fit=true)`
4. Parse B-factor range from coloring output or use:
   ```
   chimerax_run("info atoms #1 attr bfactor")
   ```
   to get min/max values

---

### Phase 3: Report Generation

Compile the Markdown report following the template below. **Number sections sequentially** — skip irrelevant sections but don't leave numbering gaps.

Write the report to `<REPORT_DIR>/report.md`.

#### Report Template

```markdown
# Structural Analysis of <TITLE> (PDB: <ID>)

## 1. Overview

| Property | Value |
|----------|-------|
| PDB ID | <ID> |
| Title | <title> |
| Resolution | <resolution> A |
| Chains | <chain list> |
| Total Atoms | <count> |
| Total Bonds | <count> |
| Total Residues | <count> |
| Protein Residues | <count> |
| Ligand | <name> (<chain> residue <number>) |
| Water Molecules | <count> |

<Brief description of the structure and its biological significance.>

![Overall structure](images/<NN>_overview.png)
*Figure 1: Overall structure colored by chain.*

## N. Secondary Structure
<(if protein) Description of fold and key features.>

![Secondary structure](images/<NN>_secondary_structure.png)
*Figure N: Secondary structure with arrow representation for beta-strands.*

## N. Chain Symmetry Analysis
<(if multimer) Table with CA atoms, RMSD. Interpretation.>

## N. Ligand: <NAME>
<(if ligand) Table with residue name, chain, number, atoms. Description.>

![Ligand overview](images/<NN>_ligand_overview.png)
*Figure N: Ligand shown as sticks.*

## N. Binding Site Analysis
<(if ligand) Sub-sections for residues, H-bonds, contacts/clashes.>

### N.1 Binding Site Residues
![Binding site](images/<NN>_binding_site.png)

### N.2 Hydrogen Bonds
| Metric | Value |
|--------|-------|
| H-bonds (ligand-protein) | <count> |

![Hydrogen bonds](images/<NN>_hbonds.png)

### N.3 Contacts and Clashes
| Analysis | Count |
|----------|-------|
| Contacts (ligand-protein) | <count> |
| Clashes (ligand-protein) | <count> |

## N. Molecular Surface Analysis

### N.1 Molecular Surface
<(if ligand) Use surface_ligand.png; (if no ligand) use surface.png>
![Surface](images/<NN>_surface_ligand.png or <NN>_surface.png)

### N.2 Electrostatic Surface Potential
![Coulombic surface](images/<NN>_coulombic.png)

## N. Dimer Interface
<(if multimer) Table with buried surface area. Interpretation.>

## N. Temperature Factors (B-factors)
| Property | Value |
|----------|-------|
| B-factor range | <min> - <max> A^2 |

![B-factor coloring](images/<NN>_bfactor.png)

## N. Summary

| Analysis | Key Finding |
|----------|-------------|
| Structure | <one-line summary> |
| Ligand Fit | <if applicable> |
| H-bond Network | <if applicable> |
| Chain RMSD | <if applicable> |
| Interface | <if applicable> |
| Flexibility | <B-factor observation> |
| Electrostatics | <surface observation> |

---

*Generated using UCSF ChimeraX via chimerax-mcp-plus MCP server*
*Analysis date: <YYYY-MM-DD>*
```

### Interpretation Guidelines

For each section, write a brief (1-3 sentence) interpretation of the results:
- **Overview**: What is this structure? Why is it important?
- **Secondary Structure**: What fold type? Key structural features?
- **Chain Alignment**: How similar are the chains? What does the RMSD indicate?
- **Ligand**: What is it? How does it bind?
- **Binding Site**: How many contacts? Good fit (0 clashes = excellent)?
- **Surface**: Is the ligand buried or exposed? Electrostatic complementarity?
- **Interface**: How extensive is the interface? Is it biologically relevant?
- **B-factors**: What regions are flexible/rigid? Functional implications?

### Error Handling

For each analysis step:
1. Attempt the command
2. If it fails, add a note to the report: *"Note: [analysis] could not be completed ([error summary])."*
3. Continue to the next section

Common recoverable errors:
- `dssp` fails on non-protein structures → skip secondary structure section
- `coulombic` requires hydrogen addition → try `addh` first, note if still fails
- `interfaces` may not be available → note and skip
- `align` fails on too few atoms → note RMSD as unavailable

### Final Steps

1. After writing the report, inform the user:
   ```
   Report saved to: <REPORT_DIR>/report.md
   Screenshots saved to: <IMAGES_DIR>/
   ```
2. Offer to open the report or run additional analyses

## Related

- **Skill**: `/explore-chimerax-commands` — Command reference for troubleshooting ChimeraX commands
- **Skill**: `/explore-chimerax` — General ChimeraX documentation reference
