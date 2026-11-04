import json
from pathlib import Path
import unittest
from check_gate import evaluate
from load_policy import load_policy

POLICY = load_policy(project_path=Path(__file__).resolve().parent.parent / "adapters/my-ea.json")
SHA = "1" * 40


def change():
    return {"id": "FIX-1", "profile": "fix", "owner": "tmlau8", "scope": ["Pure helper"], "acceptance_criteria": ["Expected output"], "evidence": {"planning": {"kind": "compact", "reference": "issue/1"}, "classification_analysis": "Inspected helper and callers; no side effects.", "verification_summary": "Regression and applicable project checks recorded."}}


def facts():
    return {"head_sha": SHA, "source": "test_fixture_not_live", "checks": [{"name": "reference-integrity", "head_sha": SHA, "producer": "github-actions", "workflow": ".github/workflows/architecture-docs.yml", "status": "completed", "conclusion": "success"}], "reviews": [{"actor": "tmlau8", "actor_type": "User", "state": "APPROVED", "commit": SHA}]}


class GateTests(unittest.TestCase):
    def test_compact_preflight(self):
        self.assertEqual(evaluate(POLICY, change(), ["MyEA/Helpers/Title.swift"], "before_delegation")["result"], "satisfied")

    def test_missing_scope_fails(self):
        c = change(); c["scope"] = []
        self.assertEqual(evaluate(POLICY, c, ["MyEA/Helper.swift"], "before_delegation")["result"], "failed")

    def test_test_changes_always_raise_risk(self):
        r = evaluate(POLICY, change(), ["MyEATests/TitleTests.swift"], "before_delegation")
        self.assertEqual(r["risk"], "high"); self.assertEqual(r["result"], "failed")

    def test_declared_low_cannot_override_policy_change(self):
        c = change(); c["risk"] = "low"
        self.assertEqual(evaluate(POLICY, c, [".governance/gates.yaml"], "before_delegation")["risk"], "high")

    def test_unknown_signal_fails_closed(self):
        c = change(); c["additional_triggers"] = ["invented"]
        with self.assertRaises(ValueError): evaluate(POLICY, c, ["a.swift"], "before_delegation")

    def test_semantic_signal_can_raise_risk(self):
        c = change(); c["additional_triggers"] = ["security"]
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_delegation")["risk"], "high")

    def test_merge_checks_current_revision_and_source(self):
        self.assertEqual(evaluate(POLICY, change(), ["a.swift"], "before_merge", facts())["result"], "satisfied")
        for field, value in [("head_sha", "2" * 40), ("producer", "fake"), ("conclusion", "skipped"), ("workflow", "other.yml")]:
            f = facts(); f["checks"][0][field] = value
            self.assertEqual(evaluate(POLICY, change(), ["a.swift"], "before_merge", f)["result"], "failed")

    def test_merge_cannot_skip_delegation_requirements(self):
        c = change(); del c["evidence"]["planning"]
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_merge", facts())["result"], "failed")

    def test_stale_or_automatic_acceptance_fails(self):
        for field, value in [("commit", "2" * 40), ("actor_type", "Bot"), ("actor", "other")]:
            f = facts(); f["reviews"][0][field] = value
            self.assertEqual(evaluate(POLICY, change(), ["a.swift"], "before_merge", f)["result"], "failed")

    def test_uncertainty_and_exception_never_become_pass(self):
        for key, value in [("uncertainty", "Unknown provider behaviour"), ("handling", "blocked"), ("handling", "exception")]:
            c = change(); c[key] = value
            self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_merge", facts())["result"], "failed")

    def test_urgent_does_not_waive_checks(self):
        c = change(); c["handling"] = "urgent"; c["expedite"] = {"actor": "tmlau8", "reason": "Incident", "follow_up": "Review tomorrow"}
        f = facts(); f["checks"] = []
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_merge", f)["result"], "failed")

    def test_other_profiles_defined_but_not_piloted(self):
        for profile in ["enhancement", "feature"]:
            c = change(); c["profile"] = profile
            self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_delegation")["result"], "failed")

    def test_release_is_separate_revision_specific_authorization(self):
        c = change(); c["evidence"].update({"readiness": "Ready", "rollback": "Revert safely"})
        f = facts()
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_release", f)["result"], "failed")
        f["release_authorization"] = {"actor": "tmlau8", "actor_type": "User", "commit": SHA, "reference": "release decision"}
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_release", f)["result"], "satisfied")

    def test_paths_are_complete_and_relative(self):
        for paths in [[], ["../gates.yaml"], ["/etc/passwd"], ["a\\b"]]:
            with self.assertRaises(ValueError): evaluate(POLICY, change(), paths, "before_delegation")

    def test_six_table_rows(self):
        self.assertEqual({(x["profile"], x["risk"]) for x in POLICY["decisions"]}, {(p, r) for p in ("fix", "enhancement", "feature") for r in ("low", "high")})

    def test_all_trigger_families_and_nested_instructions(self):
        for path, trigger in [("MyEA/Core/Auth.swift", "security"), ("MyEA/Core/Schema.swift", "data"), ("Package.swift", "dependency_tool_permission"), ("infra/service.tf", "infrastructure"), ("docs/00-product/ways-of-working.md", "assurance"), ("Modules/Child/AGENTS.md", "assurance")]:
            with self.subTest(path=path):
                r = evaluate(POLICY, change(), [path], "before_delegation")
                self.assertEqual(r["risk"], "high")
                self.assertIn(trigger, [x["trigger"] for x in r["triggers"]])

    def test_high_risk_fix_requires_added_evidence_at_each_gate(self):
        c = change()
        c["evidence"].update({"planning": {"kind": "full", "reference": "spec/1"}, "risk_analysis": "Affected authority and recovery analysed", "review_plan": "Independent review required"})
        paths = ["MyEA/Core/Auth.swift"]
        self.assertEqual(evaluate(POLICY, c, paths, "before_delegation")["result"], "satisfied")
        self.assertEqual(evaluate(POLICY, c, paths, "before_merge", facts())["result"], "failed")
        c["evidence"]["risk_review"] = "Inspectable review artifact"
        self.assertEqual(evaluate(POLICY, c, paths, "before_merge", facts())["result"], "satisfied")
        c["evidence"].update({"readiness": "Ready", "rollback": "Safe recovery", "containment": "Disable affected route", "follow_up": "Named owner to observe outcome"})
        f = facts(); f["release_authorization"] = {"actor": "tmlau8", "actor_type": "User", "commit": SHA, "reference": "release decision"}
        self.assertEqual(evaluate(POLICY, c, paths, "before_release", f)["result"], "satisfied")


if __name__ == "__main__":
    unittest.main()
