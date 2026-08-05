from __future__ import annotations
from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
executable = shutil.which("codex")

def capture(args: list[str]) -> dict:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=30
        )
        return {
            "available": True,
            "exit_code": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-20000:],
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}

if executable:
    version_result = capture([executable, "--version"])
    commands = {
        "root_help": capture([executable, "--help"]),
        "exec_help": capture([executable, "exec", "--help"]),
        "resume_help": capture([executable, "exec", "resume", "--help"]),
        "app_server_help": capture([executable, "app-server", "--help"]),
    }
    text = "\n".join(
        value.get("stdout", "") + value.get("stderr", "")
        for value in commands.values()
    ).lower()
    manifest = {
        "codex_found": True,
        "version": version_result.get("stdout", "").strip()
            or version_result.get("stderr", "").strip()
            or "unknown",
        "commands": {
            name: {
                "available": value.get("available", False),
                "exit_code": value.get("exit_code"),
            }
            for name, value in commands.items()
        },
        "features": {
            "exec_json": "--json" in text,
            "output_schema": "--output-schema" in text,
            "output_last_message": "--output-last-message" in text or " -o" in text,
            "resume": "resume" in text,
            "app_server": "app-server" in text,
            "dangerous_bypass_flag_present": "dangerously-bypass" in text,
        },
        "recommended_mode": "interactive_bootstrap_then_headless_or_orchestrated",
        "gates": [],
    }
else:
    manifest = {
        "codex_found": False,
        "version": None,
        "commands": {},
        "features": {},
        "recommended_mode": "interactive_or_install_codex_then_reprobe",
        "gates": ["codex_executable_not_found_in_current_runtime"],
    }

output = ROOT / "artifacts" / "codex_capabilities.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
