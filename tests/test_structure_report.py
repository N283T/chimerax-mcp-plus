"""Tests for structure report helper payloads."""

from chimerax_mcp.structure_report import (
    build_database_link_rows,
    build_structure_report_blocks,
    map_uniprot_feature,
)


def test_build_database_link_rows_creates_external_database_urls():
    rows = build_database_link_rows(pdb_id="1aki", uniprot_accessions=["P00698"])

    assert [row[0] for row in rows] == ["RCSB PDB", "PDBe", "PDBj", "UniProt"]
    assert rows[0][1] == {
        "text": "1AKI",
        "url": "https://www.rcsb.org/structure/1AKI",
    }
    assert rows[3][1] == {
        "text": "P00698",
        "url": "https://www.uniprot.org/uniprotkb/P00698/entry",
    }


def test_map_uniprot_feature_uses_chain_mapping_offset():
    mapped = map_uniprot_feature(
        {
            "type": "Active site",
            "uniprot_position": 53,
            "description": "Catalytic residue",
            "source_url": "https://www.uniprot.org/uniprotkb/P00698/entry#feature-viewer",
        },
        {
            "chain_id": "A",
            "uniprot_accession": "P00698",
            "uniprot_start": 19,
            "uniprot_end": 147,
            "pdb_start": 1,
            "pdb_end": 129,
        },
        model_spec="#1",
    )

    assert mapped == {
        "feature_type": "Active site",
        "description": "Catalytic residue",
        "uniprot_position": 53,
        "chain_id": "A",
        "pdb_residue": 35,
        "spec": "#1/A:35",
        "source_url": "https://www.uniprot.org/uniprotkb/P00698/entry#feature-viewer",
    }


def test_map_uniprot_feature_returns_none_when_outside_mapping():
    mapped = map_uniprot_feature(
        {"type": "Active site", "uniprot_position": 10},
        {
            "chain_id": "A",
            "uniprot_start": 19,
            "uniprot_end": 147,
            "pdb_start": 1,
            "pdb_end": 129,
        },
        model_spec="#1",
    )

    assert mapped is None


def test_build_structure_report_blocks_includes_db_and_feature_links():
    blocks = build_structure_report_blocks(
        model_spec="#1",
        model_name="1aki",
        pdb_id="1aki",
        chain_mappings=[
            {
                "chain_id": "A",
                "uniprot_accession": "P00698",
                "uniprot_start": 19,
                "uniprot_end": 147,
                "pdb_start": 1,
                "pdb_end": 129,
            }
        ],
        external_features=[
            {
                "type": "Active site",
                "uniprot_position": 53,
                "description": "Catalytic residue",
                "source_url": "https://www.uniprot.org/uniprotkb/P00698/entry#feature-viewer",
            }
        ],
    )

    table_blocks = [block for block in blocks if block["type"] == "table"]
    feature_table = next(block for block in table_blocks if block["title"] == "Mapped features")
    assert feature_table["rows"] == [
        [
            "Active site",
            53,
            "Catalytic residue",
            {"text": "#1/A:35", "spec": "#1/A:35", "action": "select"},
            {"text": "view", "spec": "#1/A:35", "action": "view"},
            {
                "text": "source",
                "url": "https://www.uniprot.org/uniprotkb/P00698/entry#feature-viewer",
            },
        ]
    ]
