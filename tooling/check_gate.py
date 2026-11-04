#!/usr/bin/env python3
"""Evaluate three pilot gates. JSON-compatible YAML avoids a parser dependency.

This command detects unmet conditions. It cannot make local work/merges impossible.
Semantic impact, supplied evidence and classification are not certified by parsing.
"""
import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
from load_policy import load_policy, ROOT

STAGES = ("before_delegation", "before_merge", "before_release")


def present(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(present(item) for item in value)
    return False


def matches(path, pattern):
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])
    )


def evaluate(policy, change, paths, stage, facts=None):
    facts = facts or {}
    errors, detections = [], []
    if stage not in STAGES:
        raise ValueError("Unknown gate")
    if not isinstance(change, dict) or not isinstance(facts, dict):
        raise ValueError("Change and facts must be objects")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise ValueError("Complete nonempty changed-path list required")
    for p in paths:
        if not p or p.startswith("/") or ".." in PurePosixPath(p).parts or "\\" in p:
            raise ValueError("Changed paths must be repository-relative POSIX paths")
    for rule in policy["triggers"]:
        hit = [p for p in paths if any(matches(p, pattern) for pattern in rule["paths"])]
        if hit:
            detections.append({"trigger": rule["id"], "paths": hit, "source": "changed_paths"})
    additional = change.get("additional_triggers", [])
    known = {r["id"] for r in policy["triggers"]}
    if not isinstance(additional, list) or any(x not in known for x in additional):
        raise ValueError("Unknown additional trigger; cannot silently classify low")
    detections.extend({"trigger": x, "source": "declared_raise_only"} for x in additional)
    # A caller-supplied risk value never overrides derived triggers.
    risk = "high" if detections else "low"
    profile = change.get("profile")
    row = next((r for r in policy["decisions"] if r["profile"] == profile and r["risk"] == risk), None)
    if row is None:
        raise ValueError("Unknown profile")
    if profile not in policy["enabled_profiles"]:
        errors.append("Profile is defined but deferred from this bug-fix-only pilot")
    for key in ("id", "owner", "scope", "acceptance_criteria"):
        if not present(change.get(key)):
            errors.append("Missing " + key)
    if change.get("uncertainty"):
        errors.append("Blocked: resolve load-bearing uncertainty through bounded investigation")
    handling = change.get("handling", "normal")
    if handling not in ("normal", "urgent", "blocked", "exception"):
        errors.append("Unknown handling state")
    if handling == "blocked":
        errors.append("Work is blocked")
    if handling == "urgent":
        exp = change.get("expedite", {})
        if not isinstance(exp, dict) or exp.get("actor") not in policy["human_authorities"] or not present(exp.get("reason")) or not present(exp.get("follow_up")):
            errors.append("Urgent route needs a named authority, reason and follow-up; no checks waived")
    if handling == "exception":
        errors.append("Scoped exception requires human disposition; evaluator does not turn it into a passed gate")
    revision = facts.get("head_sha")
    evidence = change.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be an object")
    requirements = list(dict.fromkeys(
        field for point in STAGES[:STAGES.index(stage) + 1] for field in row[point]
    ))
    for requirement in requirements:
        if requirement == "planning":
            plan = evidence.get("planning", {})
            if not isinstance(plan, dict) or plan.get("kind") != row["planning"] or not present(plan.get("reference")):
                errors.append("Planning needs a " + row["planning"] + " specification reference")
        elif requirement == "checks":
            if not revision:
                errors.append("Missing inspected revision")
            for expected in policy["required_checks"]:
                hits = [c for c in facts.get("checks", []) if isinstance(c, dict) and c.get("name") == expected["name"] and c.get("head_sha") == revision and c.get("producer") == expected["producer"] and c.get("workflow") == expected["workflow"] and c.get("status") == "completed" and c.get("conclusion") == "success"]
                if not hits:
                    errors.append("Missing/stale/failed or untrusted check: " + expected["name"])
        elif requirement == "human_acceptance":
            accepted = any(isinstance(v, dict) and v.get("actor") in policy["human_authorities"] and v.get("actor_type") == "User" and v.get("state") == "APPROVED" and v.get("commit") == revision for v in facts.get("reviews", []))
            if not revision or not accepted:
                errors.append("Missing authorised human acceptance for inspected revision")
        elif requirement == "release_authorization":
            auth = facts.get("release_authorization", {})
            if not isinstance(auth, dict) or auth.get("actor") not in policy["human_authorities"] or auth.get("actor_type") != "User" or not revision or auth.get("commit") != revision or not present(auth.get("reference")):
                errors.append("Missing authorised revision-specific release decision")
        elif not present(evidence.get(requirement)):
            errors.append("Missing evidence: " + requirement)
    return {
        "policy_version": policy["version"], "change": change.get("id"), "stage": stage,
        "profile": profile, "risk": risk, "specification": row["planning"],
        "triggers": detections, "head_sha": revision, "result": "failed" if errors else "satisfied",
        "errors": errors, "required_evidence": requirements,
        "control_status": "detected", "facts_source": facts.get("source", "supplied_unverified"),
        "limitation": "Presence checks do not certify semantic evidence or enforcement; required branch protection is separate."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(ROOT / "policy/gates.yaml"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--change", required=True)
    parser.add_argument("--paths", required=True)
    parser.add_argument("--facts")
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        def read(path):
            return json.loads(Path(path).read_text())
        result = evaluate(load_policy(args.policy, args.project), read(args.change), read(args.paths), args.stage, read(args.facts) if args.facts else {})
    except (ValueError, KeyError, TypeError, OSError) as error:
        result = {"result": "failed", "control_status": "detected", "errors": [str(error)]}
    rendered = json.dumps(result, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(rendered)
    print(rendered, end="")
    return 0 if result["result"] == "satisfied" else 1


if __name__ == "__main__":
    raise SystemExit(main())
