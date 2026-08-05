from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path

UNIT_PATTERN = re.compile(
    r"\b(?:unit|suite|ste|#)\s*[a-z0-9-]+\b",
    re.IGNORECASE,
)

POSTAL_PATTERN = re.compile(
    r"\b[a-z]\d[a-z]\s?\d[a-z]\d\b",
    re.IGNORECASE,
)

PUNCTUATION_PATTERN = re.compile(r"[^a-z0-9 ]+")

SPACE_PATTERN = re.compile(r"\s+")

STREET_REPLACEMENTS = {
    " boulevard ": " blvd ",
    " road ": " rd ",
    " street ": " st ",
    " drive ": " dr ",
    " court ": " crt ",
    " avenue ": " ave ",
    " parkway ": " pky ",
    " highway ": " hwy ",
    " lane ": " ln ",
    " place ": " pl ",
    " crescent ": " cres ",
    " trail ": " trl ",
}


def normalize_address(
    value: object,
    *,
    remove_unit: bool,
) -> str:
    text = str(value or "").casefold()

    text = POSTAL_PATTERN.sub(" ", text)
    text = re.sub(
        r"\bbrampton\b",
        " ",
        text,
    )
    text = re.sub(
        r"\bontario\b|\bon\b",
        " ",
        text,
    )

    if remove_unit:
        text = UNIT_PATTERN.sub(
            " ",
            text,
        )

    text = PUNCTUATION_PATTERN.sub(
        " ",
        text,
    )

    text = f" {SPACE_PATTERN.sub(' ', text).strip()} "

    for source, target in STREET_REPLACEMENTS.items():
        text = text.replace(
            source,
            target,
        )

    return SPACE_PATTERN.sub(
        " ",
        text,
    ).strip()


def _optional_text(
    value: object,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_permit_entity_bridge(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    try:
        permit_rows = connection.execute(
            """
            SELECT
                source_record_id,
                object_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw
            FROM
                silver.brampton_active_permit_signals
            ORDER BY
                application_at_utc DESC,
                object_id DESC
            """
        ).fetchall()

        entity_rows = connection.execute(
            """
            SELECT
                entity_id,
                canonical_business_name,
                alternate_business_name,
                canonical_address,
                postal_code,
                naics_primary,
                business_sector,
                business_subsector,
                resolution_status,
                current_status_verified
            FROM silver.odbus_entities
            WHERE lower(municipality) = 'brampton'
            ORDER BY entity_id
            """
        ).fetchall()

        entity_records = [
            {
                "entity_id": row[0],
                "canonical_business_name": row[1],
                "alternate_business_name": row[2],
                "canonical_address": row[3],
                "postal_code": row[4],
                "naics_primary": row[5],
                "business_sector": row[6],
                "business_subsector": row[7],
                "resolution_status": row[8],
                "current_status_verified": row[9],
            }
            for row in entity_rows
        ]

        full_index: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        base_index: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for entity in entity_records:
            full = normalize_address(
                entity["canonical_address"],
                remove_unit=False,
            )

            base = normalize_address(
                entity["canonical_address"],
                remove_unit=True,
            )

            if full:
                full_index[full].append(entity)

            if base:
                base_index[base].append(entity)

        resolution_rows: list[tuple[Any, ...]] = []

        candidate_rows: list[tuple[Any, ...]] = []

        distribution: Counter[str] = Counter()

        for permit in permit_rows:
            (
                source_record_id,
                object_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw,
            ) = permit

            normalized_full = normalize_address(
                address_raw,
                remove_unit=False,
            )

            normalized_base = normalize_address(
                address_raw,
                remove_unit=True,
            )

            full_matches = full_index.get(
                normalized_full,
                [],
            )

            base_matches = base_index.get(
                normalized_base,
                [],
            )

            if full_matches:
                matches = full_matches
                match_method = "exact_full"

            elif base_matches:
                matches = base_matches
                match_method = "exact_base"

            else:
                matches = []
                match_method = "none"

            matches = sorted(
                matches,
                key=lambda value: str(value["entity_id"]),
            )

            if len(matches) == 1:
                match_status = "unique"
            elif len(matches) > 1:
                match_status = "ambiguous"
            else:
                match_status = "unmatched"

            distribution[f"{match_method}_{match_status}"] += 1

            resolution_rows.append(
                (
                    source_record_id,
                    object_id,
                    permit_number,
                    application_at_utc,
                    event_type,
                    signal_strength,
                    address_raw,
                    normalized_full,
                    normalized_base,
                    match_method,
                    match_status,
                    len(matches),
                    False,
                )
            )

            for rank, entity in enumerate(
                matches,
                start=1,
            ):
                candidate_rows.append(
                    (
                        source_record_id,
                        permit_number,
                        entity["entity_id"],
                        _optional_text(entity["canonical_business_name"]),
                        _optional_text(entity["alternate_business_name"]),
                        _optional_text(entity["canonical_address"]),
                        _optional_text(entity["postal_code"]),
                        _optional_text(entity["naics_primary"]),
                        _optional_text(entity["business_sector"]),
                        _optional_text(entity["business_subsector"]),
                        _optional_text(entity["resolution_status"]),
                        bool(entity["current_status_verified"]),
                        match_method,
                        rank,
                        len(matches),
                        False,
                    )
                )

        connection.execute("BEGIN")

        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS silver
            """
        )

        connection.execute(
            """
            DROP VIEW IF EXISTS
                silver.brampton_permit_entity_unique_links
            """
        )

        connection.execute(
            """
            DROP TABLE IF EXISTS
                silver.brampton_permit_entity_match_candidates
            """
        )

        connection.execute(
            """
            DROP TABLE IF EXISTS
                silver.brampton_permit_entity_resolution
            """
        )

        connection.execute(
            """
            CREATE TABLE
                silver.brampton_permit_entity_resolution (
                    permit_source_record_id VARCHAR,
                    object_id BIGINT,
                    permit_number VARCHAR,
                    application_at_utc TIMESTAMPTZ,
                    event_type VARCHAR,
                    signal_strength VARCHAR,
                    address_raw VARCHAR,
                    normalized_full_address VARCHAR,
                    normalized_base_address VARCHAR,
                    match_method VARCHAR,
                    match_status VARCHAR,
                    candidate_count INTEGER,
                    outreach_eligible BOOLEAN
                )
            """
        )

        connection.execute(
            """
            CREATE TABLE
                silver.brampton_permit_entity_match_candidates (
                    permit_source_record_id VARCHAR,
                    permit_number VARCHAR,
                    entity_id VARCHAR,
                    canonical_business_name VARCHAR,
                    alternate_business_name VARCHAR,
                    canonical_address VARCHAR,
                    postal_code VARCHAR,
                    naics_primary VARCHAR,
                    business_sector VARCHAR,
                    business_subsector VARCHAR,
                    entity_resolution_status VARCHAR,
                    current_status_verified BOOLEAN,
                    match_method VARCHAR,
                    candidate_rank INTEGER,
                    candidate_count INTEGER,
                    outreach_eligible BOOLEAN
                )
            """
        )

        connection.executemany(
            """
            INSERT INTO
                silver.brampton_permit_entity_resolution
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            resolution_rows,
        )

        if candidate_rows:
            connection.executemany(
                """
                INSERT INTO
                    silver.brampton_permit_entity_match_candidates
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                candidate_rows,
            )

        connection.execute(
            """
            CREATE VIEW
                silver.brampton_permit_entity_unique_links
            AS
            SELECT
                resolution.permit_source_record_id,
                resolution.object_id,
                resolution.permit_number,
                resolution.application_at_utc,
                resolution.event_type,
                resolution.signal_strength,
                resolution.address_raw,
                resolution.match_method,
                candidate.entity_id,
                candidate.canonical_business_name,
                candidate.alternate_business_name,
                candidate.canonical_address,
                candidate.postal_code,
                candidate.naics_primary,
                candidate.business_sector,
                candidate.business_subsector,
                candidate.entity_resolution_status,
                candidate.current_status_verified,
                false AS outreach_eligible
            FROM
                silver.brampton_permit_entity_resolution
                    AS resolution
            INNER JOIN
                silver.brampton_permit_entity_match_candidates
                    AS candidate
            ON
                resolution.permit_source_record_id
                =
                candidate.permit_source_record_id
            WHERE
                resolution.match_status = 'unique'
                AND resolution.candidate_count = 1
            """
        )

        signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_resolution
            """,
        )

        unique_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_resolution
            WHERE match_status = 'unique'
            """,
        )

        ambiguous_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_resolution
            WHERE match_status = 'ambiguous'
            """,
        )

        unmatched_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_resolution
            WHERE match_status = 'unmatched'
            """,
        )

        candidate_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_match_candidates
            """,
        )

        unique_link_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_unique_links
            """,
        )

        unique_entity_count = _scalar(
            connection,
            """
            SELECT count(DISTINCT entity_id)
            FROM
                silver.brampton_permit_entity_unique_links
            """,
        )

        outreach_count = _scalar(
            connection,
            """
            SELECT
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_entity_resolution
                    WHERE outreach_eligible
                )
                +
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_entity_match_candidates
                    WHERE outreach_eligible
                )
            """,
        )

        verified_current_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_entity_match_candidates
            WHERE current_status_verified
            """,
        )

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    if signal_count != len(permit_rows):
        raise RuntimeError("Permit resolution count mismatch.")

    if unique_signal_count + ambiguous_signal_count + unmatched_signal_count != signal_count:
        raise RuntimeError("Permit resolution statuses do not reconcile.")

    if unique_link_count != unique_signal_count:
        raise RuntimeError("Unique link count does not match unique signal count.")

    if outreach_count != 0:
        raise RuntimeError("Permit bridge created outreach eligibility.")

    report: dict[str, Any] = {
        "model_version": ("brampton-permit-entity-bridge-v1"),
        "signal_count": signal_count,
        "unique_exact_signal_count": (unique_signal_count),
        "ambiguous_exact_signal_count": (ambiguous_signal_count),
        "unmatched_signal_count": (unmatched_signal_count),
        "candidate_row_count": candidate_count,
        "unique_link_row_count": (unique_link_count),
        "unique_link_entity_count": (unique_entity_count),
        "verified_current_candidate_count": (verified_current_count),
        "outreach_eligible_count": (outreach_count),
        "match_distribution": dict(sorted(distribution.items())),
        "resolution_table": ("silver.brampton_permit_entity_resolution"),
        "candidate_table": ("silver.brampton_permit_entity_match_candidates"),
        "unique_link_view": ("silver.brampton_permit_entity_unique_links"),
        "policy": {
            "allowed_match_methods": [
                "exact_full",
                "exact_base",
            ],
            "fuzzy_matching_enabled": False,
            "ambiguous_links_promoted": False,
            "unmatched_links_promoted": False,
            "current_status_required_for_outreach": (True),
            "outreach_eligible": False,
        },
    }

    contract_path = project_root / "docs" / "data_contracts" / "brampton_permit_entity_bridge.json"

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
