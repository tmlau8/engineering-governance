"""Read-only dashboard projections. Missing evidence never becomes compliance."""
import datetime as dt
import json
from pathlib import Path
from common import UTC, now, seconds

ROOT = Path(__file__).resolve().parent.parent


def rows(store, kind, repo="all"):
    return [r["data"] for r in store.records(kind) if repo == "all" or r["data"].get("repository") == repo]


def changes(store, repo):
    result = []
    for r in rows(store, "github:", repo):
        checks = r["checks"]
        result.append({"Repository": r["repository"], "Change": r["id"], "State": r["state"],
            "Profile": r["profile"], "Risk": r["risk"], "Triggers": ", ".join(r["triggers"]) or "No path trigger; semantic risk unverified",
            "Planning metadata": r["metadata_gate"], "Successful checks": sum(c["conclusion"] == "success" for c in checks),
            "Failed checks": sum(c["conclusion"] not in ("success", "pending", "neutral", "skipped") for c in checks),
            "Pending checks": sum(c["conclusion"] == "pending" for c in checks), "Current approvals": r["current_approvals"],
            "Checks": f"{sum(c['conclusion'] == 'success' for c in checks)} success / {sum(c['conclusion'] == 'pending' for c in checks)} pending / {sum(c['conclusion'] not in ('success', 'pending', 'neutral', 'skipped') for c in checks)} failed",
            "Independent review": r["independent_review"], "Policy at original decision": r["policy_at_change"],
            "Revision": r["head_sha"][:12], "PR evidence": r["url"], "Exact revision": r["revision_url"], "Updated": r["updated_at"]})
    return result


def rule_coverage(store, repo):
    catalogue = json.loads((ROOT / "policy/requirements.json").read_text())["rules"]
    coverage = {r["id"]: r for r in json.loads((ROOT / "policy/control-coverage.json").read_text())["requirements"]}
    records = rows(store, "github:", repo)
    adopted = rows(store, "adoption:", repo)
    result = []
    for rule in catalogue:
        code = rule["id"]
        observed = 0
        note = "No semantic evidence collected; requirement remains mandatory when applicable"
        if code == "CODE-019":
            observed = sum(r["metadata_gate"] == "metadata_satisfied" for r in records)
            note = "Planning metadata only; does not prove spec preceded implementation or is adequate"
        elif code == "CODE-020":
            observed = sum(r["state"] == "merged" for r in records)
            note = "GitHub merge observed; chat authorisation, physical human and independent review not inferred"
        elif code == "CODE-031":
            observed = sum(any(c["name"] == "reference-integrity" and c["conclusion"] == "success" for c in r["checks"]) for r in records)
            note = "CI check metadata only; no protected-producer or whole-document semantic certification"
        applicability = "conditional" if rule["applicability"] not in ("engineering_baseline", "agent_workflow_baseline") else "applicable"
        if code == "CODE-035":
            applicability = "N/A for single-user My EA; conditional for role-based projects"
        if adopted:
            applicability = adopted[0].get("applicability", {}).get(code, "unknown")
        result.append({"Rule": code, "Requirement": rule["title"], "Applicability": applicability,
            "Automation": coverage[code]["status"], "Observed subset": observed,
            "Changes inspected": len(records), "Semantic assurance": "unknown", "Enforced": "not demonstrated", "Evidence limit": note,
            "Project mechanism map": adopted[0].get("mechanism_map_url") if adopted else None})
    return result


def sessions(store, repo):
    result = []
    for r in rows(store, "usage:", repo):
        result.append({"Repository scope": r["repository"], "Session": r["session"], "Parent session": r["parent_session"] or "main",
            "Tool": r["tool"], "Agent role": r.get("agent_role", "unknown"), "Model": r["model"], "PR link": "unlinked",
            "Input tokens": r["input_tokens"], "Cached input (subset)": r["cached_input_tokens"], "Uncached input": r["uncached_input_tokens"],
            "Output tokens": r["output_tokens"], "Reasoning (subset)": r["reasoning_output_tokens"], "Total tokens": r["total_tokens"],
            "Accounting": r["usage_quality"], "Exact rollup eligible": r["included_in_exact_rollup"],
            "Reported turn seconds": r["reported_turn_seconds"], "Observed turn seconds (sum)": r["observed_turn_seconds"],
            "Turn interval seconds (union)": r["turn_interval_union_seconds"], "Session elapsed seconds": r["session_elapsed_seconds"],
            "Complete turns": r["completed_turns"], "Aborted turns": r["aborted_turns"], "Open turns": r["open_turns"],
            "Last source event": r["last_event_at"], "Association": r["association"], "Coverage": "local structured fallback; not billing or complete audit"})
    return result


def decisions(store, repo):
    result = []
    for r in rows(store, "github:", repo):
        result.append({"Repository": r["repository"], "Change": r["id"], "State": r["state"],
            "Current approvals": r["current_approvals"], "Merge actor (account)": r["merge_actor"] or "not merged",
            "Exception": r["exception_state"], "Independent review": "unknown; inspect artifacts",
            "Device evidence": r["device_evidence"], "Release evidence": r["release_evidence"], "Outcome evidence": r["outcome_evidence"],
            "Evidence": r["url"], "Merge observation": r["merge_evidence"]})
    return result


def health(store, repo):
    result = []
    at = now()
    for r in store.health():
        if repo != "all" and ":" in r["source"] and r["source"].split(":", 1)[1] not in (repo, "codex"):
            continue
        age = seconds(r["succeeded_at"], at)
        result.append({"Source": r["source"], "Status": r["status"], "Last attempt": r["attempted_at"], "Last success": r["succeeded_at"],
            "Age seconds": age, "Freshness": "never succeeded" if age is None else "stale" if age > 900 else "fresh snapshot",
            "Error code": r["error_code"] or "none", "Rows": r["row_count"]})
    return result or [{"Source": "collector", "Status": "not_collected", "Freshness": "unknown", "Error code": "NO_SUCCESSFUL_COLLECTION", "Rows": None}]


def overview(store, repo):
    changes_ = rows(store, "github:", repo)
    usage_ = rows(store, "usage:", repo)
    adoption = rows(store, "adoption:", repo)
    protection = rows(store, "protection:", repo)
    exact = [r for r in usage_ if r["included_in_exact_rollup"]]
    reported_times = [r["reported_turn_seconds"] for r in usage_ if r["reported_turn_seconds"] is not None]
    github_observed = any(r["source"].startswith("github:") and r["succeeded_at"] and (repo == "all" or r["source"] == "github:" + repo) for r in store.health())
    return [{"Changes inspected": len(changes_) if github_observed else None, "Open changes": sum(r["state"] == "open" for r in changes_) if github_observed else None,
        "Missing planning metadata": sum(r["metadata_gate"] != "metadata_satisfied" for r in changes_) if github_observed else None,
        "Policy version": adoption[0]["policy_version"] if adoption else "not observed for selected repository",
        "Policy commit": adoption[0]["policy_commit"] if adoption else None,
        "Native merge boundary": protection[0]["status"] if protection else "not observed",
        "Enforced requirements": 0, "Requirements in catalogue": 38,
        "Usage sessions": len(usage_), "Reported token sum (eligible sessions)": sum(r["total_tokens"] for r in exact) if exact else None,
        "Sessions with reported time": len(reported_times),
        "Sessions excluded from exact sum": len(usage_) - len(exact), "PR-linked usage sessions": 0,
        "Reported turn seconds (sum; overlaps)": sum(reported_times) if reported_times else None,
        "Cost": "not measured; subscription tokens are not a bill", "Snapshot": "observations and gaps; no whole-change compliance score"}]


def summary(store, repo):
    value = overview(store, repo)[0]
    fields = ["Policy version", "Policy commit", "Native merge boundary", "Enforced requirements", "Changes inspected", "Usage sessions", "Sessions excluded from exact sum", "Sessions with reported time", "PR-linked usage sessions", "Cost"]
    return [{"Measure": key, "Observation": str(value[key]) if value[key] is not None else "Unknown / not collected"} for key in fields]


def dispatch(store, view, repo):
    handlers = {"overview": overview, "summary": summary, "changes": changes, "rules": rule_coverage, "sessions": sessions, "decisions": decisions, "health": health}
    if view == "history":
        return store.history()
    if view == "attempts":
        return store.attempts()
    return handlers[view](store, repo)
