import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from github_gate import collect
from test_gate import POLICY, SHA, change


class FakeAPI:
    def __init__(self):
        import json
        self.pr = {"state": "open", "draft": False, "changed_files": 1, "body": "```governance\n" + json.dumps(change()) + "\n```", "head": {"sha": SHA}, "base": {"sha": "2" * 40}, "updated_at": "2026-11-04T00:00:00Z", "user": {"login": "tmlau8"}}
        self.files = [{"filename": "MyEA/Helpers/Title.swift"}]
        self.reviews = []
        self.comments = []
        self.checks = []
        self.run = {"head_sha": SHA, "path": ".github/workflows/architecture-docs.yml", "repository": {"full_name": "tmlau8/my-ea"}, "event": "pull_request", "check_suite_id": 50}
        self.pr_reads = 0
        self.change_during_collection = False

    def get(self, path):
        if "/actions/runs/" in path:
            return self.run
        self.pr_reads += 1
        if self.change_during_collection and self.pr_reads > 1:
            pr = copy.deepcopy(self.pr)
            pr["head"]["sha"] = "4" * 40
            return pr
        return copy.deepcopy(self.pr)

    def pages(self, path, key=None):
        if path.endswith("/files"): return self.files
        if path.endswith("/reviews"): return self.reviews
        if path.endswith("/comments"): return self.comments
        return self.checks


class AdapterTests(unittest.TestCase):
    def test_cli_uses_explicit_bounded_bundle_and_external_builder(self):
        from github_gate import main
        from load_policy import ROOT
        from review_fixtures import bundle,subject
        api=FakeAPI();api.files=[{'filename':'Auth.swift'}]
        c=change();c['evidence'].update(planning={'kind':'full','reference':'spec'},risk_analysis='impact',review_plan='reviewers',risk_review='records')
        api.pr['body']='```governance\n'+json.dumps(c)+'\n```'
        expected=subject(SHA,'2'*40,['security']);expected['change_id']=c['id']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'reviews.json';p.write_text(json.dumps(bundle(expected)))
            args=['github_gate.py','--repo','tmlau8/my-ea','--pr','1','--project',str(ROOT/'adapters/my-ea.json'),'--review-bundle',str(p),'--builder-id',expected['builder_id'],'--builder-session-id',expected['builder_session_id']]
            output=io.StringIO()
            with patch('sys.argv',args),patch.dict('os.environ',{'GH_TOKEN':'fixture-token'}),patch('github_gate.GitHub',return_value=api),contextlib.redirect_stdout(output):
                code=main()
            report=json.loads(output.getvalue())
            self.assertEqual(report['review_validation']['result'],'metadata_conforming')
            self.assertEqual(code,1) # No checks/acceptance: review metadata must not invent readiness.
            self.assertFalse(report['acceptance_basis']['physical_human_verified'])
            self.assertNotIn('fixture-token',output.getvalue())

    def test_rename_checks_old_and_new_path(self):
        api = FakeAPI(); api.files = [{"filename": "MyEA/Helper.swift", "previous_filename": "MyEA/Security.swift"}]
        _, paths, _ = collect(api, "tmlau8/my-ea", 1, POLICY)
        self.assertIn("MyEA/Security.swift", paths)

    def test_incomplete_files_fail(self):
        api = FakeAPI(); api.pr["changed_files"] = 2
        with self.assertRaises(ValueError): collect(api, "tmlau8/my-ea", 1, POLICY)

    def test_self_acceptance_is_labelled_and_revision_bound(self):
        api = FakeAPI(); api.comments = [{"user": {"login": "tmlau8", "type": "User"}, "body": "Governance acceptance: " + SHA}]
        _, _, facts = collect(api, "tmlau8/my-ea", 1, POLICY)
        self.assertTrue(facts["reviews"][0]["self_acceptance"])
        api.comments[0]["body"] = "Governance acceptance: " + "3" * 40
        self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["reviews"], [])

    def test_later_review_withdraws_approval(self):
        api = FakeAPI()
        api.reviews = [{"id": n, "state": state, "user": {"login": "tmlau8", "type": "User"}, "commit_id": SHA} for n, state in [(1, "APPROVED"), (2, "CHANGES_REQUESTED")]]
        self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["reviews"][0]["state"], "CHANGES_REQUESTED")

    def test_duplicate_metadata_blocks_fail(self):
        api = FakeAPI(); api.pr["body"] *= 2
        with self.assertRaises(ValueError): collect(api, "tmlau8/my-ea", 1, POLICY)

    def test_changed_revision_during_collection_fails(self):
        api = FakeAPI(); api.change_during_collection = True
        with self.assertRaises(ValueError): collect(api, "tmlau8/my-ea", 1, POLICY)

    def test_check_provenance_and_latest_attempt(self):
        api = FakeAPI()
        good = {"id": 1, "name": "reference-integrity", "head_sha": SHA, "details_url": "https://github.com/tmlau8/my-ea/actions/runs/10/job/20", "app": {"slug": "github-actions"}, "status": "completed", "conclusion": "success", "check_suite": {"id": 50}}
        api.checks = [good]
        self.assertEqual(len(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"]), 1)
        newer = dict(good, id=2, status="in_progress", conclusion=None)
        api.checks = [newer, good]
        checks = collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"]
        self.assertEqual(len(checks), 1)
        self.assertIsNone(checks[0]["conclusion"])
        api.checks = [dict(good, details_url="https://github.com/other/repo/actions/runs/10")]
        self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"], [])
        api.checks = [good]; api.run["head_sha"] = "4" * 40
        self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"], [])

    def test_wrong_repository_event_suite_and_modified_workflow_fail(self):
        good = {"id": 1, "name": "reference-integrity", "head_sha": SHA, "details_url": "https://github.com/tmlau8/my-ea/actions/runs/10", "app": {"slug": "github-actions"}, "status": "completed", "conclusion": "success", "check_suite": {"id": 50}}
        for key, value in [("repository", {"full_name": "other/repo"}), ("event", "push"), ("check_suite_id", 99)]:
            api = FakeAPI(); api.checks = [good]; api.run[key] = value
            self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"], [])
        for path in [".github/workflows/architecture-docs.yml", "scripts/docs/check_architecture.py"]:
            api = FakeAPI(); api.checks = [good]; api.files = [{"filename": path}]
            self.assertEqual(collect(api, "tmlau8/my-ea", 1, POLICY)[2]["checks"], [])


if __name__ == "__main__": unittest.main()
