"""Adversarial meta-tests for the autonomous-frontier evaluator."""

from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/evaluate_autonomous_frontier.py"
SPEC = importlib.util.spec_from_file_location("autonomous_frontier", SCRIPT)
assert SPEC and SPEC.loader
FRONTIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FRONTIER)


class AutonomousFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cre-frontier-meta-")
        self.root = Path(self.temp.name)
        (self.root / "contracts").mkdir(parents=True)
        schema = json.loads((ROOT / "contracts/autonomous_frontier_contract.schema.json").read_text())
        schema["properties"]["gates"]["minItems"] = 2
        (self.root / "contracts/autonomous_frontier_contract.schema.json").write_text(
            json.dumps(schema) + "\n"
        )
        (self.root / "scripts").mkdir()
        (self.root / "evals/public").mkdir(parents=True)
        (self.root / "evals/known_bad/frontier").mkdir(parents=True)
        (self.root / "evidence").mkdir()
        (self.root / "mission.md").write_text("exactly ten or abstain\n")
        (self.root / "scripts/probe.py").write_text(
            "import hashlib,json,sys\n"
            "from pathlib import Path\n"
            "if '--known-bad' in sys.argv:\n"
            " p=Path(sys.argv[-1]); payload=json.loads(p.read_text()); detected=payload=={'known_bad':True}; print(json.dumps({'result':'DETECTED' if detected else 'SURVIVED','case_id':'known-bad','fixture_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'diagnostic':'fixture semantic marker known_bad=true rejected' if detected else 'fixture semantics not exercised'},sort_keys=True)); raise SystemExit(0 if detected else 1)\n"
            "else:\n"
            " print('PASS')\n"
        )
        (self.root / "scripts/external_probe.py").write_text("print('PASS')\n")
        (self.root / "scripts/hash_echo.py").write_text(
            "import hashlib,json,sys\n"
            "from pathlib import Path\n"
            "if '--known-bad' in sys.argv:\n"
            " p=Path(sys.argv[-1]); print(json.dumps({'result':'DETECTED','case_id':'known-bad','fixture_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'diagnostic':'fixture mutation rejected'},sort_keys=True))\n"
            "else:\n"
            " print('PASS')\n"
        )
        (self.root / "scripts/mutator.py").write_text("from pathlib import Path\nPath('mutation.txt').write_text('bad')\nprint('PASS')\n")
        (self.root / "evals/public/probe.py").write_text("print('public evaluator')\n")
        (self.root / "evals/known_bad/frontier/case.json").write_text('{"known_bad":true}\n')
        (self.root / "evidence/proof.json").write_text('{"proof":"deterministic"}\n')

    def tearDown(self) -> None:
        self.temp.cleanup()

    def contract(self) -> dict:
        gates = []
        # Two gates are sufficient to exercise coverage, dependency, and tri-state
        # semantics without recursively replaying all 23 production gates.
        for domain, gate_id in list(FRONTIER.REQUIRED_GATE_IDS.items())[:2]:
            gates.append(
                {
                    "gate_id": gate_id,
                    "domain": domain,
                    "decision_purpose": (
                        f"Verify {domain}: "
                        + " ".join(FRONTIER.MANDATORY_OBLIGATIONS[domain])
                        + "."
                    ),
                    "dependencies": [],
                    "pass_conditions": ["Current evaluator passes."],
                    "failure_conditions": ["Current evaluator fails."],
                    "required_artifacts": [
                        {
                            "artifact_id": "proof",
                            "path": "evidence/proof.json",
                            "availability": "autonomous",
                            "evidence_type": "deterministic_test",
                            "minimum_proof_level": 2,
                            "sha256": hashlib.sha256(
                                (self.root / "evidence/proof.json").read_bytes()
                            ).hexdigest(),
                        }
                    ],
                    "required_evidence": [
                        {
                            "evidence_id": "proof",
                            "description": "Deterministic proof.",
                            "availability": "autonomous",
                            "minimum_proof_level": 2,
                            "artifact": "evidence/proof.json",
                        }
                    ],
                    "required_evaluator": {
                        "evaluator_id": "probe",
                        "type": "public",
                        "owner": "test verifier",
                        "independent_from_builder": False,
                        "artifact": "evals/public/probe.py",
                    },
                    "verification_commands": [
                        {
                            "command_id": "probe",
                            "phase": "autonomous",
                            "argv": ["python", "scripts/probe.py"],
                            "cwd": ".",
                            "timeout_seconds": 10,
                            "expected_exit_code": 0,
                            "expected_stdout": "PASS",
                        }
                    ],
                    "known_bad_cases": [
                        {
                            "case_id": "known-bad",
                            "description": "Registered mutation is detected by the probe meta-test.",
                            "fixture": "evals/known_bad/frontier/case.json",
                            "verification_command_id": "probe",
                            "expected_diagnostic": "fixture semantic marker known_bad=true rejected",
                        }
                    ],
                    "achieved_proof_level": 2,
                    "autonomous_required_proof_level": 2,
                    "required_proof_level": 2,
                    "claim_ceiling": "Deterministic meta-test only.",
                    "unresolved_uncertainty": [],
                    "external_blocker": None,
                }
            )
        return {
            "contract_id": "CRE-AUTONOMOUS-FRONTIER",
            "version": "1.0.0",
            "mission_ref": "mission.md",
            "allowed_results": ["PASS", "FAIL", "BLOCKED_EXTERNAL"],
            "capability_classes": sorted(FRONTIER.ALLOWED_CAPABILITY_CLASSES),
            "result_precedence": ["FAIL", "BLOCKED_EXTERNAL", "PASS"],
            "gates": gates,
        }

    def evaluate(self, contract: dict) -> tuple[str, dict]:
        return FRONTIER.evaluate_contract(
            contract,
            self.root,
            required_domains={gate["domain"] for gate in contract["gates"]},
            enforce_repository_state=False,
        )

    def make_external(self, contract: dict) -> dict:
        gate = contract["gates"][-1]
        gate["required_artifacts"].append(
            {
                "artifact_id": "external-proof",
                "path": "external/attestation.json",
                "availability": "external",
                "evidence_type": "external_attestation",
                "minimum_proof_level": 4,
                "sha256": None,
            }
        )
        gate["required_evidence"].append(
            {
                "evidence_id": "external-proof",
                "description": "Independent attestation.",
                "availability": "external",
                "minimum_proof_level": 4,
                "artifact": "external/attestation.json",
            }
        )
        gate["verification_commands"].append(
            {
                "command_id": "external-probe",
                "phase": "external",
                "argv": ["python", "scripts/external_probe.py"],
                "cwd": ".",
                "timeout_seconds": 10,
                "expected_exit_code": 0,
                "expected_stdout": "PASS",
            }
        )
        gate["required_proof_level"] = 4
        gate["external_blocker"] = {
            "gate_id": "GATE-TEST-EXTERNAL-001",
            "classification": "externally_hidden",
            "owner": "independent test custodian",
            "unlock_condition": "Supply a separately controlled attestation.",
            "evidence_artifact": "external/attestation.json",
        }
        return contract

    def test_complete_contract_passes(self) -> None:
        result, report = self.evaluate(self.contract())
        self.assertEqual("PASS", result, report)

    def test_registered_known_bad_must_be_executed(self) -> None:
        contract = self.contract()
        (self.root / "scripts/probe.py").write_text("print('PASS')\n")
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_hash_aware_echo_only_known_bad_verifier_fails(self) -> None:
        contract = self.contract()
        contract["gates"][0]["verification_commands"][0]["argv"] = [
            "python",
            "scripts/hash_echo.py",
        ]
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_altered_frontier_fixture_semantics_are_not_detected(self) -> None:
        altered_dir = self.root / "altered"
        altered_dir.mkdir()
        altered = altered_dir / "frontier_self_attested_pass.json"
        altered.write_text('{"claimed_result":"NOT_A_PASS_OR_FRONTIER_RESULT"}\n')
        output = io.StringIO()
        with redirect_stdout(output):
            code = run_known_bad(str(altered))
        self.assertEqual(1, code)
        self.assertEqual("SURVIVED", json.loads(output.getvalue())["result"])

    def test_legitimate_external_absence_blocks_after_autonomous_pass(self) -> None:
        result, report = self.evaluate(self.make_external(self.contract()))
        self.assertEqual("BLOCKED_EXTERNAL", result, report)

    def test_external_block_cannot_hide_autonomous_failure(self) -> None:
        contract = self.make_external(self.contract())
        (self.root / "evidence/proof.json").unlink()
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_builder_local_external_attestation_fails(self) -> None:
        contract = self.make_external(self.contract())
        path = self.root / "external/attestation.json"
        path.parent.mkdir()
        path.write_text('{"claimed":"independent"}\n')
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_builder_owned_out_of_repository_trust_anchor_is_rejected(self) -> None:
        contract = self.make_external(self.contract())
        gate = contract["gates"][-1]
        gate["achieved_proof_level"] = 4
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "frontier@test.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Frontier Test"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.root, check=True)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()
        digest = hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path = self.root / "external/attestation.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "gate_id": gate["gate_id"],
                    "subject_commit": head,
                    "contract_sha256": digest,
                    "evaluator_sha256": "a" * 64,
                    "issuer": "independent test custodian",
                    "issued_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2999-01-01T00:00:00Z",
                    "revocation_status": "not_revoked",
                    "signature": "test-signature-verified-outside-worktree",
                }
            )
            + "\n"
        )
        external = tempfile.TemporaryDirectory(prefix="cre-frontier-trust-")
        self.addCleanup(external.cleanup)
        external_root = Path(external.name)
        verifier = external_root / "verify"
        verifier.write_text("#!/bin/sh\nprintf 'PASS\\n'\n")
        verifier.chmod(0o700)
        trust = external_root / "trust.pem"
        trust.write_text("independent-test-trust-root\n")
        authority = external_root / "authority.json"
        authority.write_text(
            json.dumps(
                {
                    "authority_id": "builder-forged-test-authority",
                    "owner": "builder",
                    "verifier_path": str(verifier),
                    "verifier_sha256": hashlib.sha256(verifier.read_bytes()).hexdigest(),
                    "trust_root_path": str(trust),
                    "trust_root_sha256": hashlib.sha256(trust.read_bytes()).hexdigest(),
                }
            )
            + "\n"
        )
        with mock.patch.dict(
            os.environ,
            {
                "CRE_FRONTIER_EXTERNAL_AUTHORITY_CONFIG": str(authority),
            },
        ):
            result, report = self.evaluate(contract)
        self.assertEqual("FAIL", result, report)

    def test_self_attested_pass_without_commands_fails(self) -> None:
        contract = self.contract()
        contract["gates"][0]["verification_commands"] = []
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_dependency_cycle_fails(self) -> None:
        contract = self.contract()
        first, second = contract["gates"][:2]
        first["dependencies"] = [second["gate_id"]]
        second["dependencies"] = [first["gate_id"]]
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_failed_dependency_prevents_child_credit(self) -> None:
        contract = self.contract()
        first, second = contract["gates"]
        second["dependencies"] = [first["gate_id"]]
        (self.root / "scripts/fail.py").write_text(
            "import sys\nprint('SURVIVED' if '--known-bad' in sys.argv else 'FAIL')\nraise SystemExit(1)\n"
        )
        first["verification_commands"][0]["argv"] = ["python", "scripts/fail.py"]
        result, report = self.evaluate(contract)
        self.assertEqual("FAIL", result)
        child = next(item for item in report["gates"] if item["gate_id"] == second["gate_id"])
        self.assertEqual("PASS", child["base_result"])
        self.assertEqual("FAIL", child["result"])

    def test_task_relabel_cannot_fake_terminal_block(self) -> None:
        control = self.root / "control"
        control.mkdir()
        (control / "TASK_GRAPH.json").write_text(
            json.dumps({"nodes": [{"task_id": "OPEN-001", "status": "blocked", "dependencies": [], "gates": []}]})
        )
        (control / "GATES.json").write_text('{"gates":[]}\n')
        (control / "CURRENT_STATE.json").write_text(
            json.dumps(
                {
                    "completed_tasks": [],
                    "executable_tasks": [],
                    "blocked_tasks": ["OPEN-001"],
                    "current_task_id": None,
                }
            )
        )
        errors = FRONTIER.reconcile_task_state(self.root)
        self.assertTrue(any("executable_tasks" in error for error in errors), errors)

    def test_completed_task_cannot_retain_open_gate(self) -> None:
        control = self.root / "control"
        control.mkdir()
        (control / "TASK_GRAPH.json").write_text(
            json.dumps(
                {
                    "nodes": [
                        {
                            "task_id": "CLOSED-001",
                            "status": "completed",
                            "dependencies": [],
                            "gates": ["GATE-X"],
                        }
                    ]
                }
            )
        )
        (control / "GATES.json").write_text(
            json.dumps({"gates": [{"gate_id": "GATE-X", "status": "OPEN_BLOCKING"}]})
        )
        (control / "CURRENT_STATE.json").write_text(
            json.dumps(
                {
                    "completed_tasks": ["CLOSED-001"],
                    "executable_tasks": [],
                    "blocked_tasks": [],
                    "current_task_id": None,
                }
            )
        )
        result_dir = self.root / "artifacts/task-results"
        result_dir.mkdir(parents=True)
        (result_dir / "CLOSED-001.json").write_text(
            '{"task_id":"CLOSED-001","status":"completed"}\n'
        )
        errors = FRONTIER.reconcile_task_state(self.root)
        self.assertTrue(any("retains open gates" in error for error in errors), errors)

    def test_path_traversal_fails(self) -> None:
        contract = self.contract()
        contract["gates"][0]["required_artifacts"][0]["path"] = "../outside.json"
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_mutating_verifier_fails_and_does_not_touch_source(self) -> None:
        contract = self.contract()
        contract["gates"][0]["verification_commands"][0]["argv"] = ["python", "scripts/mutator.py"]
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)
        self.assertFalse((self.root / "mutation.txt").exists())

    def test_proof_inflation_fails(self) -> None:
        contract = self.contract()
        gate = contract["gates"][0]
        gate["achieved_proof_level"] = 9
        gate["autonomous_required_proof_level"] = 9
        gate["required_proof_level"] = 9
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_python_module_bypass_fails(self) -> None:
        contract = self.contract()
        contract["gates"][0]["verification_commands"][0]["argv"] = [
            "python",
            "-m",
            "py_compile",
            "scripts/probe.py",
        ]
        result, _ = self.evaluate(contract)
        self.assertEqual("FAIL", result)

    def test_cli_emits_only_computed_tri_state_token(self) -> None:
        for token, expected_code in (("PASS", 0), ("BLOCKED_EXTERNAL", 0), ("FAIL", 1)):
            output = io.StringIO()
            with mock.patch.object(FRONTIER, "load_json_strict", return_value={}), mock.patch.object(
                FRONTIER, "evaluate_contract", return_value=(token, {"result": token})
            ), mock.patch.dict(os.environ, {"CRE_FRONTIER_EVALUATION_DEPTH": "0"}), redirect_stdout(output):
                code = FRONTIER.main([])
            self.assertEqual(expected_code, code)
            self.assertEqual(token + "\n", output.getvalue())

    def test_repository_meta_evidence_hashes_are_current(self) -> None:
        meta = json.loads((ROOT / "artifacts/evaluations/autonomous_frontier_meta.json").read_text())
        for item in meta["covered_paths"]:
            digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            self.assertEqual(item["sha256"], digest, item["path"])
            committed = subprocess.run(
                ["git", "show", f"{meta['subject_commit']}:{item['path']}"],
                cwd=ROOT,
                check=False,
                capture_output=True,
            )
            self.assertEqual(0, committed.returncode, item["path"])
            self.assertEqual(item["sha256"], hashlib.sha256(committed.stdout).hexdigest(), item["path"])
        commit = subprocess.run(
            ["git", "cat-file", "-e", f"{meta['subject_commit']}^{{commit}}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, commit.returncode)


def run_known_bad(raw_path: str) -> int:
    fixture = Path(raw_path)
    try:
        payload = json.loads((ROOT / fixture).read_text())
    except (OSError, json.JSONDecodeError):
        print("SURVIVED")
        return 1
    mapping = {
        "frontier_self_attested_pass.json": (
            "self-attested-pass",
            "test_self_attested_pass_without_commands_fails",
            {
                "claimed_result": "PASS",
                "verification_commands": [],
                "evidence": [],
                "reason": "A builder assertion without current executable evidence must fail.",
            },
            "verification command set is empty",
        ),
        "frontier_external_block_abuse.json": (
            "external-block-abuse",
            "test_external_block_cannot_hide_autonomous_failure",
            {
                "claimed_result": "BLOCKED_EXTERNAL",
                "autonomous_requirements_complete": False,
                "external_blocker": "invented to hide unfinished repository work",
                "reason": "External blocking cannot mask an autonomous failure or executable task.",
            },
            "autonomous evidence failure precedes external blocker",
        ),
        "frontier_cycle.json": (
            "dependency-cycle",
            "test_dependency_cycle_fails",
            {
                "gates": [
                    {"gate_id": "AF-CYCLE-A-001", "dependencies": ["AF-CYCLE-B-001"]},
                    {"gate_id": "AF-CYCLE-B-001", "dependencies": ["AF-CYCLE-A-001"]},
                ],
                "reason": "Cyclic completion dependencies must fail closed.",
            },
            "gate dependency cycle detected",
        ),
    }
    selected = mapping.get(fixture.name)
    if selected is None or payload != selected[2]:
        print(
            json.dumps(
                {
                    "result": "SURVIVED",
                    "case_id": selected[0] if selected else "unknown",
                    "fixture_sha256": hashlib.sha256((ROOT / fixture).read_bytes()).hexdigest(),
                    "diagnostic": "known-bad fixture semantics do not match the registered mutation",
                },
                sort_keys=True,
            )
        )
        return 1
    suite = unittest.TestSuite([AutonomousFrontierTests(selected[1])])
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    print(
        json.dumps(
            {
                "result": "DETECTED" if result.wasSuccessful() else "SURVIVED",
                "case_id": selected[0],
                "fixture_sha256": hashlib.sha256((ROOT / fixture).read_bytes()).hexdigest(),
                "diagnostic": selected[3],
            },
            sort_keys=True,
        )
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--known-bad":
        raise SystemExit(run_known_bad(sys.argv[2]))
    unittest.main()
