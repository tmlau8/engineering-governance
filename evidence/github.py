"""Read-only fixed-host GitHub observations. No PR code or free text is stored."""
import base64
import datetime as dt
import json
import re
import subprocess
from common import UTC, SHA, github_url, identifier, integer, now, timestamp


class APIError(Exception):
    pass


class API:
    def __init__(self, repo):
        github_url(repo)
        self.repo = repo

    def get(self, path):
        root = "repos/" + self.repo
        if (path != root and not path.startswith(root + "/")) or ".." in path or "\\" in path:
            raise APIError("DISALLOWED_ENDPOINT")
        try:
            # gh owns authentication. No extraction, logging or persistence of its token.
            run = subprocess.run(["gh", "api", "--hostname", "github.com", "-X", "GET", path], capture_output=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired):
            raise APIError("TRANSPORT_UNAVAILABLE") from None
        if run.returncode:
            match = re.search(rb"HTTP (401|403|404|429|5\d\d)", run.stderr)
            raise APIError("GITHUB_" + match[1].decode() if match else "GITHUB_REQUEST_FAILED")
        if len(run.stdout) > 20 * 1024 * 1024:
            raise APIError("RESPONSE_TOO_LARGE")
        try:
            return json.loads(run.stdout)
        except ValueError:
            raise APIError("INVALID_JSON") from None

    def pages(self, path, key=None, max_pages=30):
        result = []
        for page in range(1, max_pages + 1):
            value = self.get(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
            batch = value.get(key) if key and isinstance(value, dict) else value
            if not isinstance(batch, list):
                raise APIError("MALFORMED_COLLECTION")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise APIError("INCOMPLETE_PAGINATION")


def governance(body):
    if not isinstance(body, str) or len(body) > 1024 * 1024:
        return None
    blocks = re.findall(r"```governance\s*\n(.*?)\n```", body, re.S)
    if len(blocks) != 1:
        return None
    try:
        value = json.loads(blocks[0])
        return value if isinstance(value, dict) else None
    except ValueError:
        return None


def observe(api, repo, number, policy):
    pr = api.get(f"repos/{repo}/pulls/{number}")
    sha, base = pr["head"]["sha"], pr["base"]["sha"]
    if not SHA.fullmatch(sha) or not SHA.fullmatch(base):
        raise APIError("INVALID_REVISION")
    files = api.pages(f"repos/{repo}/pulls/{number}/files")
    if len(files) != pr["changed_files"] or pr["changed_files"] > 3000:
        raise APIError("INCOMPLETE_PATHS")
    paths = sorted({name for f in files for name in (f.get("filename"), f.get("previous_filename")) if isinstance(name, str)})
    checks = api.pages(f"repos/{repo}/commits/{sha}/check-runs", "check_runs")
    reviews = api.pages(f"repos/{repo}/pulls/{number}/reviews")
    declaration = governance(pr.get("body"))
    # Only the existing bounded detector reads declaration free text transiently.
    from check_gate import evaluate, matches
    triggers = sorted({r["id"] for r in policy["triggers"] if any(matches(path, pattern) for path in paths for pattern in r["paths"])})
    declared = declaration or {}
    profile = declared.get("profile") if declared.get("profile") in ("fix", "enhancement", "feature") else "unknown"
    more = declared.get("additional_triggers", [])
    if isinstance(more, list):
        triggers = sorted(set(triggers) | {x for x in more if isinstance(x, str) and x in {r["id"] for r in policy["triggers"]}})
    current_reviews = {}
    for r in sorted(reviews, key=lambda x: x.get("id", 0)):
        state = r.get("state")
        if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            actor = identifier((r.get("user") or {}).get("login"))
            current_reviews[actor] = {"actor": actor, "state": state, "commit": r.get("commit_id") if isinstance(r.get("commit_id"), str) and SHA.fullmatch(r["commit_id"]) else None,
                "url": github_url(repo, f"/pull/{number}#pullrequestreview-{r['id']}") if type(r.get("id")) is int else github_url(repo, f"/pull/{number}"), "record_kind": "github_review_metadata_not_semantic_independence"}
    summaries = []
    latest = {}
    for c in checks:
        name, producer = identifier(c.get("name")), identifier((c.get("app") or {}).get("slug"))
        if name == "unknown":
            continue
        key = (name, producer)
        if key not in latest or c.get("id", 0) > latest[key].get("id", 0):
            latest[key] = c
    for (name, producer), c in latest.items():
        conclusion = c.get("conclusion") if c.get("conclusion") in ("success", "failure", "neutral", "cancelled", "skipped", "timed_out", "action_required", "startup_failure", "stale") else "pending"
        summaries.append({"name": name, "producer": producer, "conclusion": conclusion,
            "url": github_url(repo, f"/pull/{number}/checks"), "provenance": "github_check_observed_not_protected_producer"})
    metadata_gate = "missing_metadata"
    errors = []
    if declaration is not None:
        try:
            preflight = evaluate(policy, declaration, paths, "before_delegation")
            metadata_gate = "metadata_conforming" if preflight["result"] == "metadata_conforming" else "metadata_incomplete"
            # Detector errors use trusted field/check names, never raw declaration text.
            errors = [e[:160] for e in preflight["errors"][:20]]
        except (ValueError, TypeError, KeyError):
            metadata_gate = "invalid_metadata"
    current = api.get(f"repos/{repo}/pulls/{number}")
    if any(current.get(k) != pr.get(k) for k in ("updated_at", "body", "state", "draft", "merged_at")) or current["head"]["sha"] != sha or current["base"]["sha"] != base:
        raise APIError("PR_CHANGED_RETRY")
    return {
        "repository": repo, "pr": number, "id": f"PR-{number}", "state": "merged" if pr.get("merged_at") else pr["state"],
        "draft": bool(pr.get("draft")), "head_sha": sha, "base_sha": base,
        "created_at": timestamp(pr.get("created_at")), "updated_at": timestamp(pr.get("updated_at")), "merged_at": timestamp(pr.get("merged_at")),
        "url": github_url(repo, f"/pull/{number}"), "revision_url": github_url(repo, "/commit/" + sha),
        "profile": profile, "risk": "high" if triggers else "low_from_paths_only", "triggers": triggers,
        "metadata_gate": metadata_gate, "metadata_errors": errors, "checks": summaries,
        "reviews": list(current_reviews.values()), "current_approvals": sum(r["state"] == "APPROVED" and r["commit"] == sha for r in current_reviews.values()),
        "merge_actor": identifier((pr.get("merged_by") or {}).get("login")) if pr.get("merged_at") else None,
        "merge_evidence": "observed_not_proof_of_prior_readiness" if pr.get("merged_at") else "not_merged",
        "independent_review": "not_established_by_metadata", "policy_at_change": "not_established",
        "release_evidence": "not_collected", "outcome_evidence": "not_collected", "device_evidence": "not_collected",
        "exception_state": "declared_unverified" if declared.get("handling") == "exception" else "not_recorded",
        "evaluation_basis": "current_policy_metadata_gap_observation_not_historical_authorisation",
    }


def collect(api, repo, policy, days=30):
    open_prs = api.pages(f"repos/{repo}/pulls?state=open&sort=updated&direction=desc")
    cutoff = (dt.datetime.now(UTC) - dt.timedelta(days=days)).isoformat().replace("+00:00", "Z")
    closed = []
    for page in range(1, 31):
        batch = api.get(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise APIError("MALFORMED_COLLECTION")
        if any(not isinstance(p, dict) or not timestamp(p.get("updated_at")) for p in batch):
            raise APIError("SOURCE_SCHEMA_ERROR")
        closed.extend(p for p in batch if timestamp(p["updated_at"]) >= cutoff)
        if len(batch) < 100 or any(timestamp(p["updated_at"]) < cutoff for p in batch):
            break
    else:
        raise APIError("INCOMPLETE_PAGINATION")
    selected = {p["number"] for p in open_prs} | {p["number"] for p in closed if (timestamp(p.get("updated_at")) or "") >= cutoff}
    if len(selected) > 60:
        raise APIError("COLLECTION_SCOPE_LIMIT")
    return {f"{repo}#{n}": observe(api, repo, n, policy) for n in sorted(selected)}


def adoption(api, repo):
    result = api.get(f"repos/{repo}")
    branch = identifier(result["default_branch"])
    revision = api.get(f"repos/{repo}/branches/{branch}")["commit"]["sha"]
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise APIError("INVALID_REVISION")
    content = api.get(f"repos/{repo}/contents/.governance/adoption.json?ref={revision}")
    value = json.loads(base64.b64decode(content["content"]))
    source = value.get("policy_source", {})
    version = identifier(source.get("version"))
    sha = source.get("commit_sha")
    map_content = api.get(f"repos/{repo}/contents/.governance/rule-map.json?ref={revision}")
    mapping = json.loads(base64.b64decode(map_content["content"]))
    applicability = {r["id"]: r["applicability"] for r in mapping.get("requirements", []) if isinstance(r, dict) and re.fullmatch(r"CODE-\d{3}", str(r.get("id", ""))) and r.get("applicability") in ("applicable", "conditional", "not_applicable")}
    return {"repository": repo, "default_branch": branch, "policy_version": version,
        "policy_commit": sha if isinstance(sha, str) and SHA.fullmatch(sha) else None,
        "source_repository": source.get("repository") if source.get("repository") == "tmlau8/engineering-governance" else "unknown",
        "bundle_path": ".governance/baseline", "applicability": applicability,
        "mechanism_map_url": github_url(repo, "/blob/" + revision + "/.governance/rule-map.json") if isinstance(revision, str) and SHA.fullmatch(revision) else github_url(repo),
        "observation": "default_branch_adoption_metadata_observed_not_full_integrity_proof"}
