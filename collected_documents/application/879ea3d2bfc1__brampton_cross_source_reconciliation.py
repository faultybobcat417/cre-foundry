from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb
from rapidfuzz.fuzz import token_set_ratio

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path

LEGAL_SUFFIXES = {
    "co",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "lp",
    "ltd",
}

REVIEW_CLASSES = {
    "both_unique_name_conflict",
    "current_unique_aligns_historical_candidate",
    "current_unique_vs_historical_ambiguous",
    "historical_unique_aligns_current_candidate",
    "historical_unique_vs_current_ambiguous",
    "historical_unique_only",
    "current_unique_only",
    "both_ambiguous",
    "historical_ambiguous_only",
    "current_ambiguous_only",
}

CROSS_SOURCE_NAME_AGREEMENT_CLASSES = {
    "both_unique_name_exact",
    "both_unique_name_near_agreement",
}


def normalize_business_name(
    value: object,
) -> str:
    text = str(value or "").casefold()
    text = text.replace("&", " and ")

    tokens = re.findall(
        r"[a-z0-9]+",
        text,
    )

    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()

    return " ".join(tokens)


def best_name_pair(
    historical_candidates: list[dict[str, Any]],
    current_candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None

    for historical in historical_candidates:
        historical_name = str(historical.get("business_name") or "")

        historical_normalized = normalize_business_name(historical_name)

        for current in current_candidates:
            current_name = str(current.get("business_name") or "")

            current_normalized = normalize_business_name(current_name)

            if not historical_normalized or not current_normalized:
                similarity = 0.0
            else:
                similarity = float(
                    token_set_ratio(
                        historical_normalized,
                        current_normalized,
                    )
                )

            exact_normalized = (
                bool(historical_normalized) and historical_normalized == current_normalized
            )

            candidate = {
                "historical_entity_id": (historical.get("entity_id")),
                "historical_name": (historical_name),
                "historical_normalized": (historical_normalized),
                "current_global_id": (current.get("global_id")),
                "current_name": current_name,
                "current_normalized": (current_normalized),
                "exact_normalized": (exact_normalized),
                "token_set_similarity": (similarity),
            }

            if best is None:
                best = candidate
                continue

            best_similarity = float(best["token_set_similarity"])

            if similarity > best_similarity:
                best = candidate
                continue

            if (
                similarity == best_similarity
                and exact_normalized
                and not bool(best["exact_normalized"])
            ):
                best = candidate

    return best


def classify_reconciliation(
    historical_status: str,
    current_status: str,
    pair: dict[str, Any] | None,
) -> str:
    similarity = float(pair["token_set_similarity"]) if pair is not None else 0.0

    exact = bool(pair["exact_normalized"]) if pair is not None else False

    if historical_status == "unique" and current_status == "unique":
        if exact:
            return "both_unique_name_exact"

        if similarity >= 90:
            return "both_unique_name_near_agreement"

        return "both_unique_name_conflict"

    if historical_status == "ambiguous" and current_status == "unique":
        if exact or similarity >= 90:
            return "current_unique_aligns_historical_candidate"

        return "current_unique_vs_historical_ambiguous"

    if historical_status == "unique" and current_status == "ambiguous":
        if exact or similarity >= 90:
            return "historical_unique_aligns_current_candidate"

        return "historical_unique_vs_current_ambiguous"

    if historical_status == "unique" and current_status == "unmatched":
        return "historical_unique_only"

    if historical_status == "unmatched" and current_status == "unique":
        return "current_unique_only"

    if historical_status == "ambiguous" and current_status == "ambiguous":
        return "both_ambiguous"

    if historical_status == "ambiguous" and current_status == "unmatched":
        return "historical_ambiguous_only"

    if historical_status == "unmatched" and current_status == "ambiguous":
        return "current_ambiguous_only"

    if historical_status == "unmatched" and current_status == "unmatched":
        return "both_unmatched"

    return "unclassified"


def reconciliation_state(
    classification: str,
) -> str:
    mapping = {
        "both_unique_name_exact": ("corroborated_name_agreement"),
        "both_unique_name_near_agreement": ("corroborated_name_agreement"),
        "current_unique_aligns_historical_candidate": ("current_resolves_historical_ambiguity"),
        "current_unique_vs_historical_ambiguous": ("current_vs_historical_ambiguity"),
        "historical_unique_aligns_current_candidate": ("historical_aligns_current_ambiguity"),
        "historical_unique_vs_current_ambiguous": ("historical_vs_current_ambiguity"),
        "both_unique_name_conflict": ("cross_source_name_conflict"),
        "historical_unique_only": ("historical_only_address_evidence"),
        "current_unique_only": ("current_only_address_evidence"),
        "both_ambiguous": ("cross_source_address_ambiguity"),
        "historical_ambiguous_only": ("historical_address_ambiguity"),
        "current_ambiguous_only": ("current_address_ambiguity"),
        "both_unmatched": "unresolved",
        "unclassified": "unclassified",
    }

    return mapping[classification]


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_cross_source_reconciliation(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    transaction_active = False
    try:
        historical_resolution_rows = connection.execute(
            """
                SELECT
                    permit_source_record_id,
                    object_id,
                    permit_number,
                    application_at_utc,
                    event_type,
                    signal_strength,
                    address_raw,
                    match_method,
                    match_status,
                    candidate_count
                FROM
                    silver.brampton_permit_entity_resolution
                ORDER BY
                    application_at_utc DESC,
                    permit_number
                """
        ).fetchall()

        current_resolution_rows = connection.execute(
            """
                SELECT
                    permit_source_record_id,
                    permit_number,
                    match_method,
                    match_status,
                    candidate_count,
                    current_directory_address_match
                FROM
                    silver.brampton_permit_directory_resolution
                ORDER BY
                    permit_number
                """
        ).fetchall()

        historical_candidate_rows = connection.execute(
            """
                SELECT
                    permit_source_record_id,
                    entity_id,
                    canonical_business_name,
                    canonical_address,
                    naics_primary,
                    business_sector,
                    candidate_rank,
                    current_status_verified,
                    outreach_eligible
                FROM
                    silver.brampton_permit_entity_match_candidates
                ORDER BY
                    permit_source_record_id,
                    candidate_rank
                """
        ).fetchall()

        current_candidate_rows = connection.execute(
            """
                SELECT
                    permit_source_record_id,
                    directory_global_id,
                    company_name,
                    business_full_address,
                    naics_2,
                    naics_6,
                    employee_group,
                    candidate_rank,
                    directory_operational_at_snapshot,
                    permit_occupant_verified,
                    commercial_requirement_verified,
                    decision_maker_verified,
                    outreach_eligible
                FROM
                    silver.brampton_permit_directory_match_candidates
                ORDER BY
                    permit_source_record_id,
                    candidate_rank
                """
        ).fetchall()

        historical_resolution = {
            str(row[0]): {
                "permit_source_record_id": row[0],
                "object_id": row[1],
                "permit_number": row[2],
                "application_at_utc": row[3],
                "event_type": row[4],
                "signal_strength": row[5],
                "address_raw": row[6],
                "match_method": row[7],
                "match_status": row[8],
                "candidate_count": int(row[9]),
            }
            for row in historical_resolution_rows
        }

        current_resolution = {
            str(row[0]): {
                "permit_source_record_id": row[0],
                "permit_number": row[1],
                "match_method": row[2],
                "match_status": row[3],
                "candidate_count": int(row[4]),
                "current_directory_address_match": (bool(row[5])),
            }
            for row in current_resolution_rows
        }

        if set(historical_resolution) != set(current_resolution):
            raise RuntimeError("Historical and current bridge permit sets differ.")

        historical_candidates: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for row in historical_candidate_rows:
            historical_candidates[str(row[0])].append(
                {
                    "entity_id": row[1],
                    "business_name": row[2],
                    "address": row[3],
                    "naics_primary": row[4],
                    "business_sector": row[5],
                    "candidate_rank": int(row[6]),
                    "current_status_verified": (bool(row[7])),
                    "outreach_eligible": (bool(row[8])),
                }
            )

        current_candidates: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for row in current_candidate_rows:
            current_candidates[str(row[0])].append(
                {
                    "global_id": row[1],
                    "business_name": row[2],
                    "address": row[3],
                    "naics_2": row[4],
                    "naics_6": row[5],
                    "employee_group": row[6],
                    "candidate_rank": int(row[7]),
                    "directory_operational": (bool(row[8])),
                    "permit_occupant_verified": (bool(row[9])),
                    "commercial_requirement_verified": (bool(row[10])),
                    "decision_maker_verified": (bool(row[11])),
                    "outreach_eligible": (bool(row[12])),
                }
            )

        rows: list[tuple[Any, ...]] = []
        class_distribution: Counter[str] = Counter()
        state_distribution: Counter[str] = Counter()

        for permit_id, historical in historical_resolution.items():
            current = current_resolution[permit_id]

            if historical["permit_number"] != current["permit_number"]:
                raise RuntimeError("Permit-number mismatch between source bridges.")

            historical_rows = historical_candidates.get(
                permit_id,
                [],
            )

            current_rows = current_candidates.get(
                permit_id,
                [],
            )

            pair = best_name_pair(
                historical_rows,
                current_rows,
            )

            classification = classify_reconciliation(
                str(historical["match_status"]),
                str(current["match_status"]),
                pair,
            )

            state = reconciliation_state(classification)

            class_distribution[classification] += 1

            state_distribution[state] += 1

            historical_unique = (
                historical_rows[0]
                if (historical["match_status"] == "unique" and len(historical_rows) == 1)
                else None
            )

            current_unique = (
                current_rows[0]
                if (current["match_status"] == "unique" and len(current_rows) == 1)
                else None
            )

            similarity = float(pair["token_set_similarity"]) if pair is not None else None

            exact_normalized = bool(pair["exact_normalized"]) if pair is not None else False

            cross_source_alignment = classification in (
                CROSS_SOURCE_NAME_AGREEMENT_CLASSES
                | {
                    "current_unique_aligns_historical_candidate",
                    "historical_unique_aligns_current_candidate",
                }
            )

            review_required = classification in REVIEW_CLASSES

            current_operational = bool(current_rows) and all(
                bool(candidate["directory_operational"]) for candidate in current_rows
            )

            rows.append(
                (
                    permit_id,
                    historical["object_id"],
                    historical["permit_number"],
                    historical["application_at_utc"],
                    historical["event_type"],
                    historical["signal_strength"],
                    historical["address_raw"],
                    historical["match_method"],
                    historical["match_status"],
                    historical["candidate_count"],
                    current["match_method"],
                    current["match_status"],
                    current["candidate_count"],
                    bool(current["current_directory_address_match"]),
                    (historical_unique.get("entity_id") if historical_unique is not None else None),
                    (
                        historical_unique.get("business_name")
                        if historical_unique is not None
                        else None
                    ),
                    (current_unique.get("global_id") if current_unique is not None else None),
                    (current_unique.get("business_name") if current_unique is not None else None),
                    (pair.get("historical_entity_id") if pair is not None else None),
                    (pair.get("historical_name") if pair is not None else None),
                    (pair.get("current_global_id") if pair is not None else None),
                    (pair.get("current_name") if pair is not None else None),
                    similarity,
                    exact_normalized,
                    classification,
                    state,
                    cross_source_alignment,
                    review_required,
                    json.dumps(
                        [candidate["business_name"] for candidate in historical_rows],
                        sort_keys=True,
                    ),
                    json.dumps(
                        [candidate["business_name"] for candidate in current_rows],
                        sort_keys=True,
                    ),
                    current_operational,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                )
            )

        connection.execute("BEGIN")
        transaction_active = True
        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS silver
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                silver.brampton_permit_cross_source_reconciliation (
                    permit_source_record_id VARCHAR,
                    object_id BIGINT,
                    permit_number VARCHAR,
                    application_at_utc TIMESTAMPTZ,
                    event_type VARCHAR,
                    signal_strength VARCHAR,
                    address_raw VARCHAR,
                    historical_match_method VARCHAR,
                    historical_match_status VARCHAR,
                    historical_candidate_count INTEGER,
                    current_match_method VARCHAR,
                    current_match_status VARCHAR,
                    current_candidate_count INTEGER,
                    current_directory_address_match BOOLEAN,
                    historical_unique_entity_id VARCHAR,
                    historical_unique_business_name VARCHAR,
                    current_unique_global_id VARCHAR,
                    current_unique_business_name VARCHAR,
                    best_historical_entity_id VARCHAR,
                    best_historical_business_name VARCHAR,
                    best_current_global_id VARCHAR,
                    best_current_business_name VARCHAR,
                    name_similarity DOUBLE,
                    normalized_name_exact BOOLEAN,
                    reconciliation_class VARCHAR,
                    reconciliation_state VARCHAR,
                    cross_source_name_alignment BOOLEAN,
                    review_required BOOLEAN,
                    historical_candidate_names_json VARCHAR,
                    current_candidate_names_json VARCHAR,
                    current_directory_operational_at_snapshot BOOLEAN,
                    address_evidence_only BOOLEAN,
                    automatic_identity_promotion BOOLEAN,
                    permit_occupant_verified BOOLEAN,
                    commercial_requirement_verified BOOLEAN,
                    decision_maker_verified BOOLEAN,
                    outreach_eligible BOOLEAN
                )
            """
        )

        if rows:
            placeholders = ", ".join(["?"] * 37)

            connection.executemany(
                f"""
                INSERT INTO
                    silver.brampton_permit_cross_source_reconciliation
                VALUES ({placeholders})
                """,
                rows,
            )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_cross_source_review_queue
            AS
            SELECT *
            FROM
                silver.brampton_permit_cross_source_reconciliation
            WHERE review_required
            ORDER BY
                CASE signal_strength
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                application_at_utc DESC,
                permit_number
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_cross_source_agreement
            AS
            SELECT *
            FROM
                silver.brampton_permit_cross_source_reconciliation
            WHERE
                reconciliation_class IN (
                    'both_unique_name_exact',
                    'both_unique_name_near_agreement'
                )
            ORDER BY
                application_at_utc DESC,
                permit_number
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_cross_source_summary
            AS
            SELECT
                reconciliation_class,
                reconciliation_state,
                signal_strength,
                count(*) AS signals,
                count(*) FILTER (
                    WHERE review_required
                ) AS review_required_signals
            FROM
                silver.brampton_permit_cross_source_reconciliation
            GROUP BY
                reconciliation_class,
                reconciliation_state,
                signal_strength
            """
        )

        signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_reconciliation
            """,
        )

        review_queue_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_review_queue
            """,
        )

        agreement_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_agreement
            """,
        )

        alignment_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_reconciliation
            WHERE cross_source_name_alignment
            """,
        )

        safety_violation_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_reconciliation
            WHERE
                automatic_identity_promotion
                OR permit_occupant_verified
                OR commercial_requirement_verified
                OR decision_maker_verified
                OR outreach_eligible
            """,
        )

        connection.execute("COMMIT")
        transaction_active = False
    except Exception:
        if transaction_active:
            connection.execute("ROLLBACK")

        raise

    finally:
        connection.close()

    if signal_count != len(rows):
        raise RuntimeError("Cross-source reconciliation record count mismatch.")

    if sum(class_distribution.values()) != signal_count:
        raise RuntimeError("Reconciliation classes do not reconcile.")

    if safety_violation_count != 0:
        raise RuntimeError("Cross-source model violated safety flags.")

    report: dict[str, Any] = {
        "model_version": ("brampton-cross-source-reconciliation-v1"),
        "signal_count": signal_count,
        "review_queue_count": (review_queue_count),
        "cross_source_agreement_count": (agreement_count),
        "cross_source_alignment_count": (alignment_count),
        "classification_distribution": (dict(sorted(class_distribution.items()))),
        "state_distribution": dict(sorted(state_distribution.items())),
        "safety_violation_count": (safety_violation_count),
        "table": ("silver.brampton_permit_cross_source_reconciliation"),
        "review_queue_view": ("silver.brampton_permit_cross_source_review_queue"),
        "agreement_view": ("silver.brampton_permit_cross_source_agreement"),
        "summary_view": ("silver.brampton_permit_cross_source_summary"),
        "policy": {
            "name_similarity_diagnostic_only": (True),
            "near_agreement_threshold": 90,
            "automatic_identity_promotion": (False),
            "permit_occupant_verified": False,
            "commercial_requirement_verified": (False),
            "decision_maker_verified": False,
            "outreach_eligible": False,
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_cross_source_reconciliation.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
