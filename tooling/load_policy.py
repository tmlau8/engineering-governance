"""Compose the immutable baseline with an explicitly selected project adapter."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_policy(policy_path=None, project_path=None):
    baseline = json.loads(Path(policy_path or ROOT / "policy/gates.yaml").read_text())
    if baseline.get("review_requirements") != "review-requirements.json":
        raise ValueError("Unknown/missing review requirement contract")
    from review_records import load_requirements
    load_requirements()
    if project_path is None:
        raise ValueError("An explicit trusted project adapter is required")
    project = json.loads(Path(project_path).read_text())
    allowed = {"schema_version", "repository", "human_authorities", "required_checks", "trigger_paths"}
    if not isinstance(project, dict) or set(project) != allowed:
        raise ValueError("Project adapter has missing/unknown fields; baseline overrides are forbidden")
    if project["schema_version"] != 1 or not isinstance(project["repository"], str):
        raise ValueError("Unsupported project adapter")
    if not project["human_authorities"] or not all(isinstance(x, str) and x for x in project["human_authorities"]):
        raise ValueError("Named acceptance authorities are required")
    checks = project["required_checks"]
    if not isinstance(checks, list) or not checks:
        raise ValueError("At least one required check is required")
    for check in checks:
        if set(check) != {"name", "producer", "workflow", "dependency_paths"} or not all(isinstance(check[x], str) and check[x] for x in ("name", "producer", "workflow")) or not isinstance(check["dependency_paths"], list) or not all(isinstance(x, str) and x for x in check["dependency_paths"]):
            raise ValueError("Required check identity needs name, producer, workflow and dependency paths")
    triggers = project["trigger_paths"]
    if set(triggers) != {t["id"] for t in baseline["triggers"]}:
        raise ValueError("Every baseline trigger needs an explicit project path mapping")
    for trigger in baseline["triggers"]:
        paths = triggers[trigger["id"]]
        if not isinstance(paths, list) or not all(isinstance(x, str) and x for x in paths):
            raise ValueError("Trigger paths must be string lists")
        trigger["paths"] = list(dict.fromkeys(baseline["mandatory_paths"].get(trigger["id"], []) + paths))
    baseline.update({"pilot_repository": project["repository"], "human_authorities": project["human_authorities"], "required_checks": checks})
    return baseline
