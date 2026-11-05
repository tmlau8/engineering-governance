import copy
import base64
import datetime as dt
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from common import UTC, now
from github import API, APIError, adoption, collect as github_collect, governance, observe
from load_policy import ROOT, load_policy
from server import make_handler, serve
from store import Store
from usage import collect, interval_union, normalise, repository, safe_file
from views import health, overview, rule_coverage

ID = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
SHA = "a" * 40
T = dt.datetime.now(UTC).replace(microsecond=0)


def at(offset=0):
    return (T + dt.timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def token(total, offset=1, **fields):
    usage = {"input_tokens": total, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": total}
    usage.update(fields)
    return {"type": "event_msg", "timestamp": at(offset), "payload": {"type": "token_count", "info": {"total_token_usage": usage}, "private_text": "PRIVATE_SENTINEL"}}


def event(kind, turn, offset, **fields):
    return {"type": "event_msg", "timestamp": at(offset), "payload": {"type": kind, "turn_id": turn, "last_agent_message": "PRIVATE_SENTINEL", **fields}}


def meta(cwd="/repo", session=ID):
    return {"id": session, "cwd": cwd, "timestamp": at(), "source": "vscode", "cli_version": "0.164.0"}


class UsageTests(unittest.TestCase):
    def test_fractional_timestamp_order_and_duration(self):
        a, b = token(100), token(150)
        a["timestamp"], b["timestamp"] = "2026-11-04T00:00:00Z", "2026-11-04T00:00:00.100Z"
        start, end = event("task_started", "turn", 0), event("task_complete", "turn", 0)
        start["timestamp"], end["timestamp"] = a["timestamp"], b["timestamp"]
        result = normalise([a, b, start, end], meta(), "tmlau8/my-ea")
        self.assertEqual(result["reset_count"], 0)
        self.assertTrue(result["included_in_exact_rollup"])
        self.assertAlmostEqual(result["observed_turn_seconds"], 0.1, places=5)

    def test_component_counter_reset_excluded(self):
        records = [token(110, input_tokens=100, cached_input_tokens=70, output_tokens=10), token(120, 2, input_tokens=90, cached_input_tokens=10, output_tokens=30)]
        self.assertFalse(normalise(records, meta(), "tmlau8/my-ea")["included_in_exact_rollup"])

    def test_malformed_nested_source_and_aggregate_bounds(self):
        for source in [{"subagent": ["bad"]}, {"subagent": {"thread_spawn": ["bad"]}}]:
            m = meta(); m["source"] = source
            self.assertIsNone(normalise([token(100)], m, "tmlau8/my-ea")["parent_session"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scopes = [{"cwd": tmp, "repository": "tmlau8/my-ea"}]
            records = [{"type": "session_meta", "payload": meta(tmp)}, token(100), token(150, 2)]
            (root / "one.jsonl").write_text("\n".join(json.dumps(r) for r in records))
            for limit in ["MAX_FILES", "MAX_SCAN_BYTES", "MAX_EVENTS", "MAX_FILE"]:
                with patch("usage." + limit, 0), self.assertRaises(ValueError): collect(root, scopes)
            (root / "broken.jsonl").write_text("broken header")
            with self.assertRaisesRegex(ValueError, "USAGE_HEADER_INVALID"): collect(root, scopes)

    def test_cumulative_and_duplicates_not_summed(self):
        records = [token(100), token(150, 2)]
        result = normalise(records + records, meta(), "tmlau8/my-ea")
        self.assertEqual(result["total_tokens"], 150)
        self.assertTrue(result["included_in_exact_rollup"])

    def test_subsets_and_invalid_counters(self):
        r = normalise([token(130, input_tokens=100, cached_input_tokens=60, output_tokens=30, reasoning_output_tokens=10)], meta(), "tmlau8/my-ea")
        self.assertEqual((r["total_tokens"], r["uncached_input_tokens"]), (130, 40))
        bad = normalise([token(100, cached_input_tokens=101)], meta(), "tmlau8/my-ea")
        self.assertIsNone(bad["total_tokens"])
        self.assertEqual(bad["invalid_usage_records"], 1)

    def test_reset_is_lower_bound_not_invented_epoch(self):
        r = normalise([token(100), token(150, 2), token(20, 3), token(40, 4)], meta(), "tmlau8/my-ea")
        self.assertEqual(r["total_tokens"], 150)
        self.assertEqual(r["reset_count"], 1)
        self.assertFalse(r["included_in_exact_rollup"])

    def test_missing_tokens_remain_null(self):
        self.assertIsNone(normalise([], meta(), "tmlau8/my-ea")["total_tokens"])
        r = token(100); r["payload"]["info"] = None
        self.assertIsNone(normalise([r], meta(), "tmlau8/my-ea")["total_tokens"])

    def test_fork_and_mixed_model(self):
        m = meta(); m["forked_from_id"] = OTHER
        r = normalise([token(150)], m, "tmlau8/my-ea")
        self.assertFalse(r["included_in_exact_rollup"])
        records = [token(100), {"type": "turn_context", "timestamp": at(), "payload": {"model": "model-a"}}, {"type": "turn_context", "timestamp": at(2), "payload": {"model": "model-b"}}]
        self.assertEqual(normalise(records, meta(), "tmlau8/my-ea")["model"], "mixed")

    def test_duration_waiting_overlap_and_open_turn(self):
        records = [event("task_started", "turn-1", 10), event("task_complete", "turn-1", 30, duration_ms=20000), event("task_started", "turn-2", 20), event("turn_aborted", "turn-2", 40, duration_ms=20000), event("task_started", "turn-open", 50)]
        r = normalise(records, meta(), "tmlau8/my-ea")
        self.assertEqual((r["reported_turn_seconds"], r["observed_turn_seconds"], r["turn_interval_union_seconds"]), (40, 40, 30))
        self.assertEqual((r["open_turns"], r["aborted_turns"]), (1, 1))
        self.assertIn("not_compute", r["duration_kind"])

    def test_missing_end_does_not_invent_duration(self):
        r = normalise([event("task_started", "open", 1)], meta(), "tmlau8/my-ea")
        self.assertIsNone(r["observed_turn_seconds"])
        self.assertEqual(r["open_turns"], 1)

    def test_scope_rejects_broad_parent_and_unrelated(self):
        scopes = [{"cwd": "/projects/my-ea", "repository": "tmlau8/my-ea"}]
        self.assertIsNone(repository("/projects", scopes))
        self.assertIsNone(repository("/projects/other", scopes))
        self.assertEqual(repository("/projects/my-ea/child", scopes), "tmlau8/my-ea")

    def test_fragment_import_sentinel_exclusion_and_shared_fork_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "repo"; project.mkdir()
            scopes = [{"cwd": str(project), "repository": "tmlau8/my-ea"}]
            first = {"type": "session_meta", "payload": {**meta(str(project)), "instructions": "PRIVATE_SENTINEL"}}
            records = [first, token(100), token(150, 2), event("task_complete", "turn", 3, duration_ms=3000)]
            raw = "\n".join(json.dumps(r) for r in records)
            (root / "one.jsonl").write_text(raw); (root / "copy.jsonl").write_text(raw)
            result = collect(root, scopes)
            self.assertEqual(len(result), 1); self.assertEqual(result[ID]["total_tokens"], 150)
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
            first2 = {"type": "session_meta", "payload": meta(str(project), OTHER)}
            (root / "fork.jsonl").write_text("\n".join(json.dumps(r) for r in [first2, token(100), token(150, 2)]))
            result = collect(root, scopes)
            self.assertTrue(all(not r["included_in_exact_rollup"] for r in result.values()))

    def test_parent_symlink_and_malformed_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"; root.mkdir()
            outside = Path(tmp) / "outside"; outside.mkdir(); (outside / "x.jsonl").write_text("{}")
            (root / "link").symlink_to(outside, target_is_directory=True)
            self.assertFalse(safe_file(root / "link/x.jsonl", root))
            with self.assertRaises(ValueError): collect(root / "link", [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "data/evidence.sqlite"); self.addCleanup(self.store.close)

    def test_idempotence_transition_history_and_failed_collection(self):
        s = self.store; s.snapshot("source", {"one": {"state": "success"}})
        s.snapshot("source", {"one": {"state": "success"}})
        self.assertEqual(len(s.history()), 1)
        s.snapshot("source", {"one": {"state": "pending"}})
        s.snapshot("source", {"one": {"state": "success"}})
        self.assertEqual(len(s.history()), 3)
        s.failure("source", "GITHUB_429")
        self.assertEqual(s.records()[0]["data"]["state"], "success")
        self.assertEqual(s.health()[0]["status"], "error")

    def test_stale_empty_and_50_rules_are_not_green(self):
        self.assertIsNone(overview(self.store, "all")[0]["Changes inspected"])
        self.assertEqual(health(self.store, "all")[0]["Status"], "not_collected")
        self.assertEqual(len(rule_coverage(self.store, "all")), 50)
        self.assertTrue(all(r["Semantic assurance"] == "unknown" for r in rule_coverage(self.store, "all")))
        self.store.snapshot("github:tmlau8/my-ea", {}, at="2026-01-01T00:00:00Z")
        self.assertEqual(health(self.store, "all")[0]["Freshness"], "stale")
        self.assertEqual(overview(self.store, "all")[0]["Changes inspected"], 0)

    def test_reopen_permissions_and_retention(self):
        self.store.snapshot("source", {"one": {"count": 1}}, at="2020-01-01T00:00:00Z")
        self.store.prune()
        self.assertEqual(self.store.records(), [])
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        other = Store(self.store.path, readonly=True)
        self.assertEqual(other.records(), []); other.close()

    def test_missing_duration_stays_unknown_and_private_text_not_persisted(self):
        r = normalise([token(100)], meta(), "tmlau8/my-ea")
        self.store.snapshot("usage:codex", {ID: r})
        self.assertIsNone(overview(self.store, "all")[0]["Reported turn seconds (sum; overlaps)"])
        self.assertNotIn("PRIVATE_SENTINEL", self.store.path.read_bytes().decode("latin1"))


class FakeAPI:
    def __init__(self):
        self.pr = {"state": "open", "draft": False, "head": {"sha": SHA}, "base": {"sha": "b"*40}, "changed_files": 1, "body": "PRIVATE_SENTINEL", "created_at": at(), "updated_at": at(), "merged_at": None, "merged_by": None}
        self.reviews = []; self.checks = []

    def get(self, path): return copy.deepcopy(self.pr)
    def pages(self, path, key=None):
        if path.endswith("/files"): return [{"filename": "MyEA/Helper.swift"}]
        if path.endswith("/reviews"): return self.reviews
        return self.checks


class GithubEvidenceTests(unittest.TestCase):
    def setUp(self): self.policy = load_policy(project_path=ROOT / "adapters/my-ea.json")

    def test_new_detector_result_and_legacy_result_are_not_confused(self):
        from test_gate import change
        api=FakeAPI();api.pr['body']='```governance\n'+json.dumps(change())+'\n```'
        self.assertEqual(observe(api,'tmlau8/my-ea',73,self.policy)['metadata_gate'],'metadata_conforming')
        with patch('check_gate.evaluate',return_value={'result':'satisfied','errors':[]}):
            self.assertEqual(observe(api,'tmlau8/my-ea',73,self.policy)['metadata_gate'],'metadata_incomplete')

    def test_historical_merge_is_observation_not_readiness(self):
        api = FakeAPI(); api.pr.update({"state": "closed", "merged_at": at(2), "merged_by": {"login": "tmlau8", "private": "PRIVATE_SENTINEL"}})
        result = observe(api, "tmlau8/my-ea", 73, self.policy)
        self.assertEqual(result["state"], "merged")
        self.assertEqual(result["metadata_gate"], "missing_metadata")
        self.assertEqual(result["policy_at_change"], "not_established")
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))

    def test_latest_review_and_check_replace_prior_success(self):
        api = FakeAPI()
        api.reviews = [{"id": 1, "user": {"login": "tmlau8"}, "state": "APPROVED", "commit_id": SHA}, {"id": 2, "user": {"login": "tmlau8"}, "state": "DISMISSED", "commit_id": SHA}]
        api.checks = [{"id": 1, "name": "reference-integrity", "app": {"slug": "github-actions"}, "conclusion": "success"}, {"id": 2, "name": "reference-integrity", "app": {"slug": "github-actions"}, "conclusion": None}]
        result = observe(api, "tmlau8/my-ea", 73, self.policy)
        self.assertEqual(result["current_approvals"], 0)
        self.assertEqual(result["checks"][0]["conclusion"], "pending")

    def test_api_get_only_and_safe_error(self):
        api = API("tmlau8/my-ea")
        with self.assertRaises(APIError): api.get("https://elsewhere.invalid")
        failure = type("Failure", (), {"returncode": 1, "stderr": b'PRIVATE_SENTINEL HTTP 403', "stdout": b'PRIVATE_SENTINEL'})()
        with patch("github.subprocess.run", return_value=failure) as mocked:
            with self.assertRaisesRegex(APIError, '^GITHUB_403$'): api.get("repos/tmlau8/my-ea/pulls/1")
            self.assertIn("GET", mocked.call_args.args[0]); self.assertNotIn("PRIVATE_SENTINEL", str(mocked.call_args))

    def test_root_endpoint_allowed_but_adjacent_repository_rejected(self):
        api = API("tmlau8/my-ea")
        success = type("Response", (), {"returncode": 0, "stdout": b'{}'})()
        with patch("github.subprocess.run", return_value=success):
            self.assertEqual(api.get("repos/tmlau8/my-ea"), {})
            with self.assertRaises(APIError): api.get("repos/tmlau8/my-ea-other")

    def test_adoption_contents_pinned_to_one_revision(self):
        calls = []
        class AdoptionAPI:
            def get(self, path):
                calls.append(path)
                if path == "repos/tmlau8/my-ea": return {"default_branch": "master"}
                if "/branches/" in path: return {"commit": {"sha": SHA}}
                value = {"policy_source": {"version": "1.0.0-rc.1", "commit_sha": SHA}} if "adoption.json" in path else {"requirements": [{"id": "CODE-001", "applicability": "applicable"}]}
                return {"content": base64.b64encode(json.dumps(value).encode()).decode()}
        result = adoption(AdoptionAPI(), "tmlau8/my-ea")
        self.assertIn(SHA, result["mechanism_map_url"])
        self.assertTrue(all("ref=" + SHA in p for p in calls if "/contents/" in p))

    def test_all_recent_closed_pages_and_scope_failure(self):
        class ClosedAPI:
            def pages(self, path): return []
            def get(self, path):
                page = int(path.rsplit("page=", 1)[1])
                return [{"number": i, "updated_at": at()} for i in range(1, 101)] if page == 1 else [{"number": 101, "updated_at": at()}]
        with self.assertRaisesRegex(APIError, "COLLECTION_SCOPE_LIMIT"): github_collect(ClosedAPI(), "tmlau8/my-ea", self.policy)
        class ElevenAPI(ClosedAPI):
            def get(self, path): return [{"number": i, "updated_at": at()} for i in range(1, 12)]
        with patch("github.observe", side_effect=lambda api, repo, n, policy: {"pr": n}):
            self.assertEqual(len(github_collect(ElevenAPI(), "tmlau8/my-ea", self.policy)), 11)

    def test_racing_revision_and_incomplete_pagination_fail_closed(self):
        api = FakeAPI(); original = api.get
        count = 0
        def changing(path):
            nonlocal count
            count += 1; value = original(path)
            if count > 1: value["head"]["sha"] = "c" * 40
            return value
        api.get = changing
        with self.assertRaisesRegex(APIError, "PR_CHANGED_RETRY"): observe(api, "tmlau8/my-ea", 73, self.policy)
        with patch.object(API, "get", return_value=[{}] * 100), self.assertRaisesRegex(APIError, "INCOMPLETE_PAGINATION"):
            API("tmlau8/my-ea").pages("repos/tmlau8/my-ea/pulls", max_pages=2)


class RuntimeTests(unittest.TestCase):
    def test_dashboard_preserves_full_detail_and_never_embeds_secrets(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dashboard_build_test", ROOT / "dashboard/build.py")
        build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
        document = build.dashboard()
        details = next(p for p in document["panels"] if p["type"] == "row")
        self.assertTrue(details["collapsed"])
        self.assertEqual({p["targets"][0]["url"].split("/api/")[1].split("?")[0] for p in details["panels"]}, {"sessions", "changes"})
        self.assertTrue(all("transformations" not in p for p in details["panels"]))
        with tempfile.TemporaryDirectory() as tmp:
            build.provision(Path(tmp), {"api_token": "PRIVATE_SENTINEL", "grafana_password": "PASSWORD_SENTINEL", "grafana_secret_key": "KEY_SENTINEL"})
            raw = (Path(tmp) / "dashboards/engineering.json").read_text()
            self.assertNotIn("SENTINEL", raw)
            self.assertEqual((Path(tmp) / "provisioning/datasources/evidence.yaml").stat().st_mode & 0o777, 0o600)

    def test_spawn_failure_stops_actual_owned_child(self):
        import manage
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp); (runtime / "logs").mkdir(); (runtime / "settings.json").write_text('{}')
            binary = runtime / "software/bin/grafana"; binary.parent.mkdir(parents=True); binary.touch()
            actual_popen = subprocess.Popen; children = []
            def spawn(*args, **kwargs):
                if args[0][0] == "ps": return actual_popen(*args, **kwargs)
                if children: raise OSError("injected spawn failure")
                child = actual_popen([sys.executable, "-c", "import time;time.sleep(20)", str(manage.ROOT)], start_new_session=True)
                children.append(child); return child
            try:
                with patch.object(manage, "RUNTIME", runtime), patch.object(manage, "GRAFANA", binary.parent.parent), patch.object(manage.subprocess, "Popen", side_effect=spawn):
                    with self.assertRaises(OSError): manage.start()
                children[0].wait(timeout=2)
                self.assertFalse((runtime / "processes.json").exists())
            finally:
                for child in children:
                    if child.poll() is None: child.kill(); child.wait()

    def test_journal_failure_rolls_back_in_memory_child(self):
        import manage
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp); (runtime / "logs").mkdir(); (runtime / "settings.json").write_text('{}')
            binary = runtime / "software/bin/grafana"; binary.parent.mkdir(parents=True); binary.touch()
            child = type("Child", (), {"pid": 1234})()
            original = manage.write_private; calls = 0
            def write(path, value):
                nonlocal calls
                calls += 1
                if calls == 2: raise OSError("injected journal failure")
                return original(path, value)
            with patch.object(manage, "RUNTIME", runtime), patch.object(manage, "GRAFANA", binary.parent.parent), patch.object(manage, "write_private", side_effect=write), patch.object(manage.subprocess, "Popen", return_value=child), patch.object(manage, "stop_children") as stop:
                with self.assertRaises(OSError): manage.start()
                stop.assert_called_once_with({"collector": 1234})

    def test_log_caps_and_owned_purge_then_fresh_store(self):
        import manage
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"; (runtime / "logs").mkdir(parents=True)
            (runtime / "logs/lifecycle.log").write_text("x" * (1024 * 1024))
            (runtime / ".owned-runtime.json").write_text(json.dumps({"project": str(manage.ROOT)}))
            (runtime / "secrets").mkdir(); (runtime / "secrets/credentials.json").write_text("PRIVATE_SENTINEL")
            db = runtime / "data/evidence.sqlite"; store = Store(db); store.snapshot("source", {"one": {"state": "ok"}}); store.close()
            upstream = Path(tmp) / "upstream"; upstream.write_text("preserve")
            with patch.object(manage, "RUNTIME", runtime), patch.object(manage.time, "sleep"):
                manage.lifecycle("SERVICES_STARTED")
                self.assertTrue((runtime / "logs/lifecycle.log.1").exists())
                manage.purge()
                self.assertFalse(db.exists()); self.assertFalse((runtime / "secrets").exists()); self.assertFalse((runtime / "logs").exists())
                self.assertEqual(upstream.read_text(), "preserve")
                store = Store(db); self.assertEqual(store.history(), []); store.close()


class APIBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); s = Store(self.root/'data/evidence.sqlite'); s.close()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.root, 'test-secret', 0, 3001, ['tmlau8/my-ea']))
        self.port = self.server.server_port
        self.server.RequestHandlerClass = make_handler(self.root, 'test-secret', self.port, 3001, ['tmlau8/my-ea'])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    def request(self, path='/api/overview', headers=None, method='GET'):
        h={'Authorization':'Bearer test-secret'}; h.update(headers or {})
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path, headers=h, method=method)
        try:
            with urllib.request.urlopen(req) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)

    def test_auth_host_origin_and_no_writes(self):
        self.assertEqual(self.request()[0],200)
        self.assertEqual(self.request(headers={'Authorization':''})[0],401)
        self.assertEqual(self.request(headers={'Host':'evil.invalid'})[0],403)
        self.assertEqual(self.request(headers={'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request(method='POST')[0],405)

    def test_query_and_path_boundaries_and_no_secret(self):
        self.assertEqual(self.request('/api/overview?repo=elsewhere')[0],400)
        self.assertEqual(self.request('/api/overview?url=https://elsewhere.invalid')[0],400)
        self.assertEqual(self.request('/api/../secrets')[0],404)
        self.assertNotIn('test-secret',json.dumps(self.request()[1]))
        with self.assertRaises(ValueError):serve(self.root,'0.0.0.0')


if __name__ == '__main__':unittest.main()
