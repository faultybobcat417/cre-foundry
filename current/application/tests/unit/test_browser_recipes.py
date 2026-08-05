from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.browser_recipes import (
    audit_browser_recipes,
)


def _write_source_config(
    root: Path,
) -> None:
    path = root / "config" / "source_operations.json"

    path.parent.mkdir(parents=True)

    path.write_text(
        json.dumps({"sources": {"test_source": {}}}),
        encoding="utf-8",
    )


def _policy() -> dict[str, object]:
    return {
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


def test_design_pending_recipe_is_safe(
    tmp_path: Path,
) -> None:
    _write_source_config(tmp_path)

    path = tmp_path / "config" / "browser_recipes.json"

    path.write_text(
        json.dumps(
            {
                "policies": _policy(),
                "recipes": {
                    "template": {
                        "source_id": "test_source",
                        "version": "1",
                        "status": "design_pending",
                        "start_url": None,
                        "allowed_domains": [],
                        "navigation_mode": ("dom_first_visual_fallback"),
                        "steps": [],
                        "assertions": [],
                        "evidence": {"capture_dom": True},
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = audit_browser_recipes(
        tmp_path,
        write_contract=False,
    )

    assert report["ready"] is True

    assert report["design_pending_count"] == 1

    assert report["executable_count"] == 0


def test_executable_recipe_is_rejected_while_disabled(
    tmp_path: Path,
) -> None:
    _write_source_config(tmp_path)

    path = tmp_path / "config" / "browser_recipes.json"

    path.write_text(
        json.dumps(
            {
                "policies": _policy(),
                "recipes": {
                    "recipe": {
                        "source_id": "test_source",
                        "version": "1",
                        "status": "executable",
                        "start_url": ("https://example.com"),
                        "allowed_domains": ["example.com"],
                        "navigation_mode": ("dom_first_visual_fallback"),
                        "steps": [{"action": "observe"}],
                        "assertions": [{"type": "url"}],
                        "evidence": {"capture_dom": True},
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = audit_browser_recipes(
        tmp_path,
        write_contract=False,
    )

    assert report["ready"] is False

    assert "executable_recipes_present_while_runtime_disabled" in report["violations"]
