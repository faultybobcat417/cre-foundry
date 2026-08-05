from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def audit_browser_recipes(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    recipe_config = _load_object(project_root / "config" / "browser_recipes.json")

    source_config = _load_object(project_root / "config" / "source_operations.json")

    expected_policy: dict[str, Any] = {
        "operating_mode": "shadow",
        "browser_execution_enabled": False,
        "computer_vision_execution_enabled": False,
        "api_first": True,
        "network_capture_before_dom": True,
        "dom_before_computer_vision": True,
        "human_review_on_ambiguity": True,
        "captcha_bypass_allowed": False,
        "access_control_bypass_allowed": False,
        "destructive_actions_allowed": False,
        "automatic_outreach_allowed": False,
    }

    raw_policy = recipe_config.get("policies")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Browser-recipe policies must be a JSON object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != expected_policy:
        raise RuntimeError("Browser-recipe policy does not match the required safety policy.")

    raw_recipes = recipe_config.get("recipes")

    if not isinstance(
        raw_recipes,
        dict,
    ):
        raise RuntimeError("Browser recipes must be a JSON object.")

    raw_sources = source_config.get("sources")

    if not isinstance(
        raw_sources,
        dict,
    ):
        raise RuntimeError("Source operations contain no sources.")

    source_ids = {str(source_id) for source_id in raw_sources}

    recipes = []
    violations = []

    executable_count = 0
    design_pending_count = 0

    for recipe_id, raw_recipe in sorted(raw_recipes.items()):
        if not isinstance(
            recipe_id,
            str,
        ):
            violations.append("recipe_id_not_string")
            continue

        if not isinstance(
            raw_recipe,
            dict,
        ):
            violations.append(f"{recipe_id}:recipe_not_object")
            continue

        source_id = raw_recipe.get("source_id")

        status = raw_recipe.get("status")

        allowed_domains = raw_recipe.get("allowed_domains")

        start_url = raw_recipe.get("start_url")

        steps = raw_recipe.get("steps")

        assertions = raw_recipe.get("assertions")

        evidence = raw_recipe.get("evidence")

        recipe_violations = []

        if (
            not isinstance(
                source_id,
                str,
            )
            or source_id not in source_ids
        ):
            recipe_violations.append("unknown_source")

        if status not in {
            "design_pending",
            "disabled",
            "review_ready",
            "executable",
        }:
            recipe_violations.append("invalid_status")

        if not isinstance(
            allowed_domains,
            list,
        ) or not all(
            isinstance(
                domain,
                str,
            )
            for domain in allowed_domains
        ):
            recipe_violations.append("invalid_domain_allowlist")

        if not isinstance(
            steps,
            list,
        ):
            recipe_violations.append("steps_not_list")

        if not isinstance(
            assertions,
            list,
        ):
            recipe_violations.append("assertions_not_list")

        if not isinstance(
            evidence,
            dict,
        ):
            recipe_violations.append("evidence_not_object")

        executable = status == "executable"

        if executable:
            executable_count += 1

            if (
                not isinstance(
                    start_url,
                    str,
                )
                or not start_url
            ):
                recipe_violations.append("executable_missing_start_url")

            if not allowed_domains:
                recipe_violations.append("executable_missing_domains")

            if not steps:
                recipe_violations.append("executable_missing_steps")

            if not assertions:
                recipe_violations.append("executable_missing_assertions")

        elif status == "design_pending":
            design_pending_count += 1

        for violation in recipe_violations:
            violations.append(f"{recipe_id}:{violation}")

        recipes.append(
            {
                "recipe_id": recipe_id,
                "source_id": source_id,
                "status": status,
                "start_url": start_url,
                "allowed_domain_count": (
                    len(allowed_domains)
                    if isinstance(
                        allowed_domains,
                        list,
                    )
                    else 0
                ),
                "step_count": (
                    len(steps)
                    if isinstance(
                        steps,
                        list,
                    )
                    else 0
                ),
                "assertion_count": (
                    len(assertions)
                    if isinstance(
                        assertions,
                        list,
                    )
                    else 0
                ),
                "executable": executable,
                "violations": (recipe_violations),
            }
        )

    if executable_count != 0:
        violations.append("executable_recipes_present_while_runtime_disabled")

    report = {
        "model_version": ("cre-foundry-browser-recipes-v1"),
        "recipe_count": len(recipes),
        "design_pending_count": (design_pending_count),
        "executable_count": (executable_count),
        "violation_count": len(violations),
        "violations": violations,
        "recipes": recipes,
        "policy": policy,
        "ready": (not violations),
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "browser_recipes.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
