import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
from check_gate import evaluate
from load_policy import load_policy

POLICY = load_policy(project_path=Path(__file__).resolve().parent.parent / "adapters/my-ea.json")
SHA = "1" * 40


def change():
    return {"id": "FIX-1", "profile": "fix", "owner": "tmlau8", "scope": ["Pure helper"], "acceptance_criteria": ["Expected output"], "evidence": {"planning": {"kind": "compact", "reference": "issue/1"}, "classification_analysis": "Inspected helper and callers; no side effects.", "verification_summary": "Regression and applicable project checks recorded."}}


def facts():
    return {"head_sha": SHA, "source": "test_fixture_not_live", "checks": [{"name": "reference-integrity", "head_sha": SHA, "producer": "github-actions", "workflow": ".github/workflows/architecture-docs.yml", "status": "completed", "conclusion": "success"}], "reviews": [{"actor": "tmlau8", "actor_type": "User", "state": "APPROVED", "commit": SHA}]}


class GateTests(unittest.TestCase):
    def test_cli_exit_follows_new_metadata_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=root/'change.json';p=root/'paths.json';c.write_text(json.dumps(change()));p.write_text('["a.swift"]')
            tool=Path(__file__).resolve().parent.parent
            command=[sys.executable,'-B',str(tool/'tooling/check_gate.py'),'--project',str(tool/'adapters/my-ea.json'),'--change',str(c),'--paths',str(p),'--stage','before_delegation']
            run=subprocess.run(command,capture_output=True,text=True);self.assertEqual(run.returncode,0);self.assertEqual(json.loads(run.stdout)['result'],'metadata_conforming')
            c.write_text('{"id":"one","id":"two"}');self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
    def test_acceptance_basis_and_active_dissent_are_explicit(self):
        f=facts(); f['pr_author']='tmlau8'; f['reviews'][0].update(source='github_comment_self_acceptance',self_acceptance=True)
        report=evaluate(POLICY,change(),['a.swift'],'before_merge',f)
        self.assertEqual(report['result'],'metadata_conforming')
        self.assertEqual(report['acceptance_basis']['records'][0]['basis'],'self_acceptance')
        self.assertFalse(report['acceptance_basis']['physical_human_verified'])
        f['reviews'].append({'actor':'other-human','actor_type':'User','state':'CHANGES_REQUESTED','commit':SHA})
        self.assertEqual(evaluate(POLICY,change(),['a.swift'],'before_merge',f)['result'],'failed')

    def test_security_and_dependency_routing_regressions(self):
        for name in ['TokenStore.swift','CredentialManager.swift','SessionManager.swift','Login.swift','Info.plist','Cargo.lock','Package.resolved','pnpm-lock.yaml']:
            self.assertEqual(evaluate(POLICY,change(),['Modules/Nested/'+name],'before_delegation')['risk'],'high',name)
        for name in ['ClockView.swift','BlockedStateView.swift','Title.swift']:
            self.assertEqual(evaluate(POLICY,change(),['Modules/Nested/'+name],'before_delegation')['risk'],'low',name)

    def test_placeholder_evidence_is_never_called_verified(self):
        c=change();c['evidence']['classification_analysis']='n/a'
        r=evaluate(POLICY,c,['a.swift'],'before_delegation')
        self.assertEqual(r['result'],'metadata_conforming');self.assertIn('metadata_only',r['assurance'])
        self.assertNotIn('satisfied',r.values())

    def test_high_merge_has_no_green_when_review_transport_unavailable(self):
        c=change();c['evidence'].update(planning={'kind':'full','reference':'spec'},risk_analysis='scope',review_plan='reviewers',risk_review='placeholder')
        r=evaluate(POLICY,c,['Auth.swift'],'before_merge',facts())
        self.assertEqual(r['result'],'failed');self.assertEqual(r['review_validation']['result'],'unavailable')

    def test_compact_preflight(self):
        self.assertEqual(evaluate(POLICY, change(), ["MyEA/Helpers/Title.swift"], "before_delegation")["result"], "metadata_conforming")

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
        self.assertEqual(evaluate(POLICY, change(), ["a.swift"], "before_merge", facts())["result"], "metadata_conforming")
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
        self.assertEqual(evaluate(POLICY, c, ["a.swift"], "before_release", f)["result"], "metadata_conforming")

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
        self.assertEqual(evaluate(POLICY, c, paths, "before_delegation")["result"], "metadata_conforming")
        self.assertEqual(evaluate(POLICY, c, paths, "before_merge", facts())["result"], "failed")
        c["evidence"]["risk_review"] = "Inspectable review artifact"
        f = facts(); f["base_sha"] = "b"*40
        from review_fixtures import bundle, subject
        expected = subject(SHA, "b"*40, ["security"]); expected["change_id"] = c["id"]
        f.update({k:expected[k] for k in ("builder_id","builder_session_id")})
        f["review_bundle"] = bundle(expected)
        self.assertEqual(evaluate(POLICY, c, paths, "before_merge", f)["result"], "metadata_conforming")
        c["evidence"].update({"readiness": "Ready", "rollback": "Safe recovery", "containment": "Disable affected route", "follow_up": "Named owner to observe outcome"})
        f["release_authorization"] = {"actor": "tmlau8", "actor_type": "User", "commit": SHA, "reference": "release decision"}
        self.assertEqual(evaluate(POLICY, c, paths, "before_release", f)["result"], "metadata_conforming")


if __name__ == "__main__":
    unittest.main()
