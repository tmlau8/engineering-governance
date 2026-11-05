"""Bounded review metadata validation; never authenticates a reviewer or fetches evidence."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 64
MAX_ARTIFACTS = 256
SHA = re.compile(r"[0-9a-f]{40}\Z")


def loads(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON_BYTE_LIMIT")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("DUPLICATE_JSON_KEY")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def read(path):
    with Path(path).open("rb") as handle:
        return loads(handle.read(MAX_BYTES + 1))


def validator():
    try:
        import rfc3339_validator  # Required explicitly: absent format plugins must not silently skip.
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        raise ValueError("VALIDATOR_UNAVAILABLE") from None
    schema = read(ROOT / "policy/schemas/review-record.schema.json")
    def refs(value):
        if isinstance(value, dict):
            if "$ref" in value and not value["$ref"].startswith("#/"):
                raise ValueError("EXTERNAL_SCHEMA_REFERENCE_FORBIDDEN")
            for item in value.values(): refs(item)
        elif isinstance(value, list):
            for item in value: refs(item)
    refs(schema)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def artifacts_of(record):
    result = list(record.get("artifacts_inspected", []))
    if record.get("account_reviewed") is not None:
        result.append(record["account_reviewed"])
    for claim in record.get("claims_examined", []): result.extend(claim.get("evidence", []))
    for counter in record.get("counterexamples_attempted", []):
        if counter.get("resolution") is not None: result.append(counter["resolution"])
    return result


def load_requirements():
    value = read(ROOT / 'policy/review-requirements.json')
    keys = {'schema_version','stage','applies_when','all_triggered','per_detected_trigger','counted_outcomes','principal'}
    if not isinstance(value,dict) or set(value)!=keys or type(value['schema_version']) is not int or value['schema_version']!=1 or value['stage']!='before_merge' or value['applies_when']!='any_trigger_detected' or value['counted_outcomes']!=['cleared']:
        raise ValueError('UNSUPPORTED_REVIEW_REQUIREMENTS')
    for key, roles in [('all_triggered',{'adversarial','quality'}),('per_detected_trigger',{'specialist'})]:
        mapping=value[key]
        if not isinstance(mapping,dict) or set(mapping)!=roles or any(type(n) is not int or not 1<=n<=MAX_RECORDS for n in mapping.values()):
            raise ValueError('UNSUPPORTED_REVIEW_REQUIREMENTS')
    if not isinstance(value['principal'],str) or not value['principal'].strip():raise ValueError('UNSUPPORTED_REVIEW_REQUIREMENTS')
    return value


def validate_set(bundle, subject, requirements=None):
    """subject is supplied by the trusted caller, never inferred from candidate records."""
    check = validator()
    required = {"repository", "change_id", "policy_version", "head_sha", "base_sha", "trigger_ids", "builder_id", "builder_session_id"}
    if not isinstance(subject, dict) or not required <= set(subject) or set(subject) - required - {"account_sha256"}:
        raise ValueError("INVALID_EXTERNAL_SUBJECT")
    if not SHA.fullmatch(subject.get("head_sha", "")) or not SHA.fullmatch(subject.get("base_sha", "")):
        raise ValueError("INVALID_EXTERNAL_REVISION")
    if not isinstance(bundle, dict) or set(bundle) != {"records", "artifacts"}:
        raise ValueError("INVALID_REVIEW_BUNDLE")
    records, encoded = bundle["records"], bundle["artifacts"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS or not isinstance(encoded, dict) or len(encoded) > MAX_ARTIFACTS:
        raise ValueError("REVIEW_BUNDLE_LIMIT")
    known = {r["id"] for r in read(ROOT / "policy/gates.yaml")["triggers"]}
    triggers = subject["trigger_ids"]
    if not isinstance(triggers, list) or len(triggers) != len(set(triggers)) or any(t not in known for t in triggers):
        raise ValueError("INVALID_EXTERNAL_TRIGGERS")
    material, size = {}, 0
    for reference, value in encoded.items():
        if not isinstance(reference, str) or len(reference) > 512 or not isinstance(value, str) or len(value) > MAX_BYTES * 2:
            raise ValueError("INVALID_ARTIFACT_BYTES")
        try: raw = base64.b64decode(value, validate=True)
        except ValueError: raise ValueError("INVALID_ARTIFACT_BYTES") from None
        size += len(raw)
        if size > MAX_BYTES: raise ValueError("ARTIFACT_BYTE_LIMIT")
        material[reference] = hashlib.sha256(raw).hexdigest()
    entries, rejected, fatal = {}, [], []
    if subject['policy_version'] != read(ROOT/'policy/gates.yaml')['version']:
        fatal.append('UNSUPPORTED_POLICY_VERSION')
    for index, record in enumerate(records):
        errors = []
        if list(check.iter_errors(record)):
            rejected.append({"index": index, "reasons": ["SCHEMA_INVALID"]}); fatal.append("SCHEMA_INVALID"); continue
        rid = record["record_id"]
        if rid in entries:
            fatal.append("DUPLICATE_RECORD_ID"); continue
        entries[rid] = record
        if any(record[k] != subject[k] for k in ("repository", "change_id", "policy_version")) or record["reviewed_revision"]["head_sha"] != subject["head_sha"] or record["reviewed_revision"].get("base_sha") != subject["base_sha"]:
            errors.append("SUBJECT_MISMATCH")
        if any(t not in known for t in record.get("trigger_ids", [])):
            errors.append("UNKNOWN_TRIGGER")
        rule_ids = {r["id"] for r in read(ROOT / "policy/requirements.json")["rules"]}
        if any(code not in rule_ids for code in record["rule_ids"]): errors.append("UNKNOWN_RULE")
        for artifact in artifacts_of(record):
            if material.get(artifact["reference"]) != artifact["sha256"]:
                errors.append("ARTIFACT_UNRESOLVED_OR_CHANGED")
            if artifact.get("revision") and artifact["revision"] not in (subject["head_sha"], subject["base_sha"]):
                errors.append("ARTIFACT_REVISION_MISMATCH")
        builder, reviewer, independence = record["builder"], record["reviewer"], record["independence"]
        if builder["id"] != subject["builder_id"] or builder.get("session_id") != subject["builder_session_id"]:
            errors.append("BUILDER_SUBJECT_MISMATCH")
        if record["outcome"] == "cleared" and not any(a.get("revision") == subject["head_sha"] for a in record.get("artifacts_inspected", [])):
            errors.append("NO_HEAD_BOUND_INSPECTED_ARTIFACT")
        if record["review_type"] == "principal" and (not subject.get("account_sha256") or record["account_reviewed"]["sha256"] != subject["account_sha256"]):
            errors.append("ACCOUNT_EXTERNAL_DIGEST_MISMATCH_OR_UNAVAILABLE")
        if builder["id"] == reviewer["id"] or (builder.get("session_id") and builder.get("session_id") == reviewer.get("session_id")):
            errors.append("SELF_REVIEW")
        basis = independence["basis"]
        if basis == "none" or independence["builder_conclusions_as_premises"]:
            errors.append("INDEPENDENCE_NOT_DECLARED")
        if independence["credential_separation"] != "separate":
            errors.append("CREDENTIAL_SEPARATION_NOT_ESTABLISHED")
        if reviewer["kind"] == "agent":
            if basis not in ("separate_agent_session", "different_model_family"):
                errors.append("IDENTITY_BASIS_CONFLICT")
            if basis == "different_model_family" and independence.get("same_model_family_as_builder") is not False:
                errors.append("MODEL_RELATION_CONFLICT")
            if basis == "different_model_family" and builder["kind"] != "agent":
                errors.append("MODEL_RELATION_CONFLICT")
            if independence.get("same_model_as_builder") is True and independence.get("same_model_family_as_builder") is False:
                errors.append("MODEL_RELATION_CONFLICT")
            if builder["kind"] == "agent":
                bm, rm = builder["provenance"]["model"], reviewer["provenance"]["model"]
                if "unavailable" not in (bm, rm) and independence.get("same_model_as_builder") is not None and (bm == rm) != independence["same_model_as_builder"]:
                    errors.append("MODEL_RELATION_CONFLICT")
                bf, rf = builder["provenance"].get("model_family"), reviewer["provenance"].get("model_family")
                if basis == "different_model_family" and (not bf or not rf or "unavailable" in (bf, rf)):
                    errors.append("MODEL_FAMILY_UNAVAILABLE")
                if bf and rf and "unavailable" not in (bf, rf) and independence.get("same_model_family_as_builder") is not None and (bf == rf) != independence["same_model_family_as_builder"]:
                    errors.append("MODEL_RELATION_CONFLICT")
        elif basis != "different_human":
            errors.append("IDENTITY_BASIS_CONFLICT")
        if record["outcome"] != "cleared": errors.append("OUTCOME_NOT_CLEARED")
        if any(c["outcome"] != "held" and not c.get("resolution") for c in record.get("counterexamples_attempted", [])):
            errors.append("COUNTEREXAMPLE_UNRESOLVED")
        if any(f["disposition"]["state"] == "open" for f in record.get("findings", [])):
            errors.append("FINDING_OPEN")
        if any(f["severity"] in ("high", "critical") and f["disposition"]["state"] != "fixed" for f in record.get("findings", [])):
            errors.append("BLOCKING_FINDING_REQUIRES_NEW_CLEARANCE")
        if errors: rejected.append({"record_id": rid, "reasons": sorted(set(errors))})
    # A superseding non-clear record invalidates the prior clear record too.
    replaced, children = set(), {}
    for rid, record in entries.items():
        old = record.get("supersedes")
        if not old: continue
        if old not in entries or old == rid:
            fatal.append("SUPERSESSION_DANGLING_OR_SELF"); continue
        previous = entries[old]
        if any(previous[k] != record[k] for k in ("repository", "change_id", "policy_version", "review_type")) or previous["reviewer"]["id"] != record["reviewer"]["id"]:
            fatal.append("SUPERSESSION_SUBJECT_CONFLICT")
        if old in children: fatal.append("SUPERSESSION_FORK")
        children[old] = rid; replaced.add(old)
    for start in entries:
        seen, cursor = set(), start
        while cursor in children:
            if cursor in seen: fatal.append("SUPERSESSION_CYCLE"); break
            seen.add(cursor); cursor = children[cursor]
    rejected_ids = {r.get("record_id") for r in rejected}
    accepted = [r for rid, r in entries.items() if rid not in replaced and rid not in rejected_ids]
    trusted = load_requirements()
    requirements = trusted if requirements is None else requirements
    if requirements != trusted:
        raise ValueError("UNTRUSTED_REVIEW_REQUIREMENTS")
    missing = []
    if triggers:
        for role, minimum in requirements["all_triggered"].items():
            if sum(r["review_type"] == role for r in accepted) < minimum: missing.append("MISSING_" + role.upper())
        for trigger in triggers:
            if sum(r["review_type"] == "specialist" and trigger in r.get("trigger_ids", []) for r in accepted) < requirements['per_detected_trigger']['specialist']: missing.append("MISSING_SPECIALIST_" + trigger)
    active_rejections = [r for r in rejected if r.get("record_id") not in replaced]
    return {"result": "failed" if fatal or missing or active_rejections else "metadata_conforming", "accepted_record_ids": [r["record_id"] for r in accepted], "superseded_record_ids": sorted(replaced), "rejected": rejected,
        "errors": sorted(set(fatal + missing)), "assurance": "declared_record_metadata_and_supplied_byte_integrity_only",
        "gaps": ["review_origin_not_authenticated", "credential_separation_declared_not_verified", "review_quality_and_independence_not_certified"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True); parser.add_argument("--subject", required=True)
    args = parser.parse_args()
    try: result = validate_set(read(args.bundle), read(args.subject))
    except Exception: result = {"result": "failed", "errors": ["REVIEW_VALIDATION_UNAVAILABLE_OR_INVALID"]}
    print(json.dumps(result, indent=2)); return 0 if result["result"] == "metadata_conforming" else 1


if __name__ == "__main__": raise SystemExit(main())
