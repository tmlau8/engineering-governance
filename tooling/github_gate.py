#!/usr/bin/env python3
"""Read-only GitHub adapter. Never checks out or executes PR content."""
import argparse
import fnmatch
import json
import os
import re
import urllib.request
from pathlib import Path
from check_gate import evaluate
from load_policy import load_policy
from review_records import loads, read


class GitHub:
    def __init__(self, token):
        self.token = token

    def get(self, path):
        req = urllib.request.Request("https://api.github.com/" + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    def pages(self, path, key=None):
        result = []
        for page in range(1, 31):
            batch = self.get(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
            batch = batch[key] if key else batch
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise ValueError("Pagination limit reached; incomplete evidence cannot pass")


def collect(api, repo, number, policy):
    pr = api.get(f"repos/{repo}/pulls/{number}")
    if pr["state"] != "open" or pr["draft"]:
        raise ValueError("Pilot requires an open, non-draft PR")
    if pr["changed_files"] > 3000:
        raise ValueError("PR file-list limit exceeded")
    blocks = re.findall(r"```governance\s*\n(.*?)\n```", pr.get("body") or "", re.S)
    if len(blocks) != 1:
        raise ValueError("PR body needs exactly one governance JSON block")
    change = loads(blocks[0])
    files = api.pages(f"repos/{repo}/pulls/{number}/files")
    if len(files) != pr["changed_files"]:
        raise ValueError("Incomplete changed-file list")
    paths = sorted({name for f in files for name in (f["filename"], f.get("previous_filename")) if name})
    sha = pr["head"]["sha"]
    # A matching workflow name/provider cannot authenticate a PR-modified workflow.
    changed = set(paths)
    checks = []
    latest_checks = {}
    for c in api.pages(f"repos/{repo}/commits/{sha}/check-runs", "check_runs"):
        if not any(e["name"] == c["name"] for e in policy["required_checks"]):
            continue
        url = c.get("details_url") or ""
        match = re.match(r"https://github\.com/" + re.escape(repo) + r"/actions/runs/(\d+)(?:/|$)", url)
        if not match:
            continue
        run = api.get(f"repos/{repo}/actions/runs/{match[1]}")
        if run["head_sha"] != sha or run.get("repository", {}).get("full_name") != repo or run.get("event") != "pull_request" or run.get("check_suite_id") != c.get("check_suite", {}).get("id") or run.get("check_suite_id") is None:
            continue
        producer = c.get("app", {}).get("slug")
        workflow = run["path"].split("@")[0]
        dependencies = [pattern for expected in policy["required_checks"] if expected["workflow"] == workflow for pattern in expected["dependency_paths"]]
        if workflow in changed or any(fnmatch.fnmatchcase(path, pattern) for path in changed for pattern in dependencies):
            continue
        identity = (c["name"], producer, workflow)
        # A newer pending/failed attempt must supersede an earlier success.
        if identity not in latest_checks or c["id"] > latest_checks[identity]["id"]:
            latest_checks[identity] = {"id": c["id"], "name": c["name"], "head_sha": c["head_sha"], "producer": producer, "workflow": workflow, "status": c["status"], "conclusion": c["conclusion"]}
    checks = list(latest_checks.values())
    latest = {}
    for review in sorted(api.pages(f"repos/{repo}/pulls/{number}/reviews"), key=lambda v: v["id"]):
        if review["state"] != "COMMENTED":
            latest[review["user"]["login"]] = {"actor": review["user"]["login"], "actor_type": review["user"]["type"], "state": review["state"], "commit": review["commit_id"], "source": "github_review"}
    # Solo acceptance is explicit and labelled, rather than fabricated peer review.
    marker = "Governance acceptance: " + sha
    for comment in api.pages(f"repos/{repo}/issues/{number}/comments"):
        user = comment["user"]
        if user["login"] == pr["user"]["login"] and user["login"] not in latest and comment["body"].strip() == marker:
            latest[user["login"]] = {"actor": user["login"], "actor_type": user["type"], "state": "APPROVED", "commit": sha, "source": "github_comment_self_acceptance", "self_acceptance": True}
    current = api.get(f"repos/{repo}/pulls/{number}")
    if any(current[k] != pr[k] for k in ("updated_at", "body", "state", "draft")) or current["head"]["sha"] != sha or current["base"]["sha"] != pr["base"]["sha"]:
        raise ValueError("PR changed during collection; rerun the gate")
    return change, paths, {"source": "github_api_snapshot", "head_sha": sha, "base_sha": pr["base"]["sha"], "pr_author": pr["user"]["login"], "checks": checks, "reviews": list(latest.values())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--stage", default="before_merge", choices=["before_delegation", "before_merge"])
    p.add_argument("--report")
    p.add_argument("--project", required=True)
    p.add_argument("--review-bundle", help="Explicit operator-supplied bounded local review bundle; never read from a PR path")
    p.add_argument("--builder-id", help="Externally supplied logical builder identity, not inferred from review records")
    p.add_argument("--builder-session-id", help="Externally supplied builder session")
    args = p.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo) or args.pr <= 0:
            raise ValueError("Invalid repository/PR")
        policy = load_policy(project_path=args.project)
        if args.repo != policy["pilot_repository"]:
            raise ValueError("Repository differs from the selected pilot")
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError("GitHub credential with read access required in GH_TOKEN; actual authority may be broader")
        change, paths, facts = collect(GitHub(token), args.repo, args.pr, policy)
        if args.review_bundle:
            if not args.builder_id or not args.builder_session_id:
                raise ValueError("Review bundle requires external builder identity/session")
            facts.update(review_bundle=read(args.review_bundle), builder_id=args.builder_id, builder_session_id=args.builder_session_id,
                source="github_snapshot_with_operator_supplied_review_metadata")
        report = evaluate(policy, change, paths, args.stage, facts)
    except Exception as error:
        report = {"result": "failed", "control_status": "detected", "errors": [str(error)]}
    data = json.dumps(report, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(data)
    print(data, end="")
    return 0 if report["result"] == "metadata_conforming" else 1


if __name__ == "__main__":
    raise SystemExit(main())
