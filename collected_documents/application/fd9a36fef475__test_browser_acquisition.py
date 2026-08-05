from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.browser_acquisition import (
    audit_browser_acquisition,
)


def test_browser_acquisition_is_governed_and_disabled(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config" / "browser_acquisition.json"

    config_path.parent.mkdir(parents=True)

    config_path.write_text(
        json.dumps(
            {
                "config_version": "test",
                "enabled": False,
                "operating_mode": "shadow",
                "acquisition_precedence": [
                    "authorized_official_api",
                    "authorized_network_response_capture",
                    "authorized_bulk_or_file_download",
                    "browser_dom_or_accessibility_tree",
                    "computer_vision_fallback",
                    "human_exception_review",
                ],
                "controls": {
                    "domain_allowlist_required": True,
                    "source_authorization_required": True,
                    "isolated_browser_profile_required": True,
                    "credential_reference_required_for_authenticated_sources": True,
                    "request_rate_limit_required": True,
                    "concurrency_limit_required": True,
                    "navigation_recipe_version_required": True,
                    "dom_capture_required": True,
                    "screenshot_before_visual_action_required": True,
                    "screenshot_after_visual_action_required": True,
                    "network_archive_when_available": True,
                    "content_checksum_required": True,
                    "layout_change_quarantine_required": True,
                    "human_review_on_ambiguity_required": True,
                    "captcha_bypass_allowed": False,
                    "access_control_bypass_allowed": False,
                    "destructive_actions_allowed": False,
                    "automatic_outreach_allowed": False,
                },
                "runtime": {
                    "browser_execution_enabled": False,
                    "computer_vision_execution_enabled": False,
                    "macos_screen_recording_permission": ("manual_confirmation_required"),
                    "macos_accessibility_permission": ("manual_confirmation_required"),
                    "macos_automation_permission": ("manual_confirmation_required"),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = audit_browser_acquisition(
        tmp_path,
        write_contract=False,
    )

    assert report["governance_ready"] is True
    assert report["execution_ready"] is False
    assert report["enabled"] is False

    assert report["controls"]["captcha_bypass_allowed"] is False

    assert report["controls"]["access_control_bypass_allowed"] is False

    assert report["controls"]["automatic_outreach_allowed"] is False
