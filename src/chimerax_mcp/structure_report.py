"""Helpers for ChimeraX rich structure reports."""

from __future__ import annotations

from typing import Any


def normalize_pdb_id(pdb_id: str | None) -> str | None:
    """Return an uppercase PDB ID, or None for empty input."""
    if pdb_id is None:
        return None
    normalized = pdb_id.strip().upper()
    return normalized or None


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_database_link_rows(
    pdb_id: str | None = None,
    uniprot_accessions: list[str] | None = None,
) -> list[list[Any]]:
    """Build rich-report rows for common structure/protein database links."""
    rows: list[list[Any]] = []
    normalized_pdb = normalize_pdb_id(pdb_id)
    if normalized_pdb is not None:
        pdb_lower = normalized_pdb.lower()
        rows.extend(
            [
                [
                    "RCSB PDB",
                    {
                        "text": normalized_pdb,
                        "url": f"https://www.rcsb.org/structure/{normalized_pdb}",
                    },
                ],
                [
                    "PDBe",
                    {
                        "text": normalized_pdb,
                        "url": f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pdb_lower}",
                    },
                ],
                [
                    "PDBj",
                    {
                        "text": normalized_pdb,
                        "url": f"https://pdbj.org/mine/summary/{normalized_pdb}",
                    },
                ],
            ]
        )

    for accession in uniprot_accessions or []:
        normalized_accession = accession.strip()
        if not normalized_accession:
            continue
        rows.append(
            [
                "UniProt",
                {
                    "text": normalized_accession,
                    "url": f"https://www.uniprot.org/uniprotkb/{normalized_accession}/entry",
                },
            ]
        )
    return rows


def _feature_position(feature: dict[str, Any]) -> int | None:
    for key in ("uniprot_position", "position", "uniprot_begin", "begin"):
        position = _int_value(feature.get(key))
        if position is not None:
            return position
    return None


def map_uniprot_feature(
    feature: dict[str, Any],
    chain_mapping: dict[str, Any],
    model_spec: str,
) -> dict[str, Any] | None:
    """Map a single UniProt feature position onto a ChimeraX residue spec."""
    uniprot_position = _feature_position(feature)
    uniprot_start = _int_value(chain_mapping.get("uniprot_start"))
    uniprot_end = _int_value(chain_mapping.get("uniprot_end"))
    pdb_start = _int_value(chain_mapping.get("pdb_start"))
    pdb_end = _int_value(chain_mapping.get("pdb_end"))
    chain_id = _text(chain_mapping.get("chain_id"))

    if (
        uniprot_position is None
        or uniprot_start is None
        or uniprot_end is None
        or pdb_start is None
        or pdb_end is None
        or not chain_id
    ):
        return None
    if not uniprot_start <= uniprot_position <= uniprot_end:
        return None

    pdb_residue = pdb_start + (uniprot_position - uniprot_start)
    if not min(pdb_start, pdb_end) <= pdb_residue <= max(pdb_start, pdb_end):
        return None

    spec = f"{model_spec}/{chain_id}:{pdb_residue}"
    return {
        "feature_type": _text(feature.get("type") or feature.get("feature_type"), "Feature"),
        "description": _text(feature.get("description") or feature.get("comment")),
        "uniprot_position": uniprot_position,
        "chain_id": chain_id,
        "pdb_residue": pdb_residue,
        "spec": spec,
        "source_url": _text(feature.get("source_url") or feature.get("url")),
    }


def _uniprot_accessions(
    chain_mappings: list[dict[str, Any]] | None,
    external_features: list[dict[str, Any]] | None,
) -> list[str]:
    accessions: set[str] = set()
    for item in chain_mappings or []:
        accession = _text(item.get("uniprot_accession") or item.get("accession"))
        if accession:
            accessions.add(accession)
    for item in external_features or []:
        accession = _text(item.get("uniprot_accession") or item.get("accession"))
        if accession:
            accessions.add(accession)
    return sorted(accessions)


def _matching_mapping(
    feature: dict[str, Any],
    chain_mappings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    feature_accession = _text(feature.get("uniprot_accession") or feature.get("accession"))
    candidates = chain_mappings
    if feature_accession:
        candidates = [
            mapping
            for mapping in chain_mappings
            if _text(mapping.get("uniprot_accession") or mapping.get("accession"))
            == feature_accession
        ]
    for mapping in candidates:
        if map_uniprot_feature(feature, mapping, model_spec="#0") is not None:
            return mapping
    return candidates[0] if candidates else None


def _feature_rows(
    external_features: list[dict[str, Any]] | None,
    chain_mappings: list[dict[str, Any]] | None,
    model_spec: str,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    mappings = chain_mappings or []
    for feature in external_features or []:
        mapping = _matching_mapping(feature, mappings)
        mapped = map_uniprot_feature(feature, mapping, model_spec) if mapping is not None else None
        if mapped is None:
            continue
        source_cell: Any = ""
        if mapped["source_url"]:
            source_cell = {"text": "source", "url": mapped["source_url"]}
        rows.append(
            [
                mapped["feature_type"],
                mapped["uniprot_position"],
                mapped["description"],
                {"text": mapped["spec"], "spec": mapped["spec"], "action": "select"},
                {"text": "view", "spec": mapped["spec"], "action": "view"},
                source_cell,
            ]
        )
    return rows


def build_structure_report_blocks(
    model_spec: str,
    model_name: str | None = None,
    pdb_id: str | None = None,
    chain_mappings: list[dict[str, Any]] | None = None,
    external_features: list[dict[str, Any]] | None = None,
    include_db_links: bool = True,
) -> list[dict[str, Any]]:
    """Build rich-report blocks for a structure plus caller-provided annotations."""
    accessions = _uniprot_accessions(chain_mappings, external_features)
    blocks: list[dict[str, Any]] = [
        {
            "type": "cards",
            "items": [
                {
                    "label": "Model",
                    "value": {"text": model_spec, "spec": model_spec, "action": "view"},
                },
                {"label": "Name", "value": model_name or ""},
                {"label": "PDB", "value": normalize_pdb_id(pdb_id) or ""},
                {"label": "UniProt", "value": ", ".join(accessions)},
            ],
        }
    ]

    if chain_mappings:
        blocks.append(
            {
                "type": "table",
                "title": "Chain mappings",
                "columns": ["Chain", "UniProt", "UniProt range", "PDB range", "Select", "View"],
                "rows": [
                    [
                        _text(mapping.get("chain_id")),
                        _text(mapping.get("uniprot_accession") or mapping.get("accession")),
                        f"{mapping.get('uniprot_start', '')}-{mapping.get('uniprot_end', '')}",
                        f"{mapping.get('pdb_start', '')}-{mapping.get('pdb_end', '')}",
                        {
                            "text": "select",
                            "spec": f"{model_spec}/{_text(mapping.get('chain_id'))}",
                            "action": "select",
                        },
                        {
                            "text": "view",
                            "spec": f"{model_spec}/{_text(mapping.get('chain_id'))}",
                            "action": "view",
                        },
                    ]
                    for mapping in chain_mappings
                    if _text(mapping.get("chain_id"))
                ],
            }
        )

    if include_db_links:
        db_rows = build_database_link_rows(pdb_id=pdb_id, uniprot_accessions=accessions)
        if db_rows:
            blocks.append(
                {
                    "type": "table",
                    "title": "Database links",
                    "columns": ["Database", "Link"],
                    "rows": db_rows,
                }
            )

    feature_rows = _feature_rows(external_features, chain_mappings, model_spec)
    if feature_rows:
        blocks.append(
            {
                "type": "table",
                "title": "Mapped features",
                "columns": ["Feature", "UniProt pos", "Description", "Residue", "View", "Source"],
                "rows": feature_rows,
            }
        )
    elif external_features:
        blocks.append(
            {
                "type": "callout",
                "tone": "warning",
                "title": "No mapped features",
                "text": (
                    "External features were provided, but none matched the supplied chain mappings."
                ),
            }
        )

    return blocks
