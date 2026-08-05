from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
from pathlib import Path
from typing import Any

from cre_foundry.source_operations import _atomic_json


def audit_browser_acquisition(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config_path = project_root / "config" / "browser_acquisition.json"

    config = json.loads(config_path.read_text(encoding="utf-8"))

    controls = config["controls"]

    required_false = {
        "captcha_bypass_allowed": False,
        "access_control_bypass_allowed": False,
        "destructive_actions_allowed": False,
        "automatic_outreach_allowed": False,
    }

    for key, expected in required_false.items():
        if controls.get(key) != expected:
            raise RuntimeError(f"Unsafe browser policy: {key}")

    if config["operating_mode"] != "shadow":
        raise RuntimeError("Browser acquisition must remain in shadow mode.")

    package_names = (
        "playwright",
        "selenium",
        "opencv-python",
        "opencv-python-headless",
        "pillow",
        "mss",
        "pyautogui",
        "pytesseract",
        "easyocr",
        "torch",
        "torchvision",
        "transformers",
    )

    packages = {}

    for package_name in package_names:
        try:
            version = importlib.metadata.version(package_name)

            packages[package_name] = {
                "installed": True,
                "version": version,
            }

        except importlib.metadata.PackageNotFoundError:
            packages[package_name] = {
                "installed": False,
                "version": None,
            }

    applications = {}

    for application_path in (
        Path("/Applications/Google Chrome.app"),
        Path("/Applications/Chromium.app"),
        Path("/Applications/Firefox.app"),
        Path("/Applications/Safari.app"),
        Path("/Applications/Microsoft Edge.app"),
    ):
        applications[application_path.name] = {
            "installed": application_path.exists(),
            "path": str(application_path),
        }

    executables = {
        name: shutil.which(name)
        for name in (
            "screencapture",
            "osascript",
            "tesseract",
            "ffmpeg",
            "chromium",
            "google-chrome",
            "playwright",
        )
    }

    installed_browser_count = sum(1 for payload in applications.values() if payload["installed"])

    report = {
        "model_version": ("cre-foundry-browser-acquisition-v1"),
        "enabled": config["enabled"],
        "operating_mode": config["operating_mode"],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "acquisition_precedence": config["acquisition_precedence"],
        "controls": controls,
        "runtime_policy": config["runtime"],
        "applications": applications,
        "executables": executables,
        "packages": packages,
        "installed_browser_count": (installed_browser_count),
        "governance_ready": True,
        "execution_ready": False,
        "status": ("governance_ready_runtime_disabled"),
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "browser_acquisition.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
