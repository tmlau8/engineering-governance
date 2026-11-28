# POLICY-002 — Review records and agentic policy candidate

Owner: Albert. Candidate 1.1.0-rc.1; no release, merge or adoption-pin change.
Implementation and independent validation: [verification record](../verification/POLICY-002.md).
This branch is stacked above the open evidence/dashboard PR. Existing immutable
release and My EA adoption remain on 1.0.0-rc.1. New policy requirements describe
the candidate target; they do not certify the current shared-account setup.

## Contract and acceptance

Adopt the user's seven-file draft after correcting the independently identified
weaknesses. Preserve CODE-001–038 and add CODE-039–050, a strict JSON Schema,
synthetic examples and a bounded validator for revision-bound review sets.
Concurrently remove misleading gate success terminology, expose account/self
acceptance basis and active dissent, and correct demonstrated path misrouting.
No automatic identity provisioning, release signing, hosted evidence custody,
Claude integration or My EA application change is included.

Required proof: valid schema/set; negative/malformed/conditional/unavailable/
supersession/evidence-binding cases; missing validator dependency fails closed;
no arbitrary evidence URL/file fetch; date formats and duplicate keys checked;
external subject mismatch rejected; complete per-trigger review set; acceptance
report and security/lock near misses; all existing consumers/tests; reproducible
bundle and supported Python floor; independent final specialist/Quality and
adversarial reviews. Metadata conformance is never human-identity verification.

## Decisions before implementation

- Pinned jsonschema 4.25.1 supports Python >=3.9 in its official PyPI metadata:
  https://pypi.org/pypi/jsonschema/4.25.1/json. Use Draft202012Validator, explicit
  date-time checking and local-only schema references; do not hand-roll JSON Schema.
- Trusted inputs supply repository, change ID, policy version, head/base SHA and
  detected triggers. Records cannot establish their own subject by mutual agreement.
- Evidence arrives only as bounded bytes in an explicitly supplied JSON bundle.
  Each referenced artifact carries SHA256 checked against those bytes. There is
  no record-directed network/filesystem access. Origin/authenticity remains declared
  unless an external trusted collector establishes it; byte integrity is not review truth.
- Only cleared records count. Conditional clearance needs a fresh cleared record.
  Unavailable records do not require invented findings. Principal records bind the
  exact account digest; supported claims have evidence. Unresolved refutations or
  untestable load-bearing counterexamples cannot clear.
- Reject duplicate IDs, forks/cycles/dangling supersession, subject mismatches,
  inconsistent identities/model declarations, stale heads and unresolved artifacts.
  A later non-clear record supersedes its earlier clearance. One specialist may
  cover multiple explicitly named triggers within its bounded scope.
- Separate bounded sessions are distinct from credential isolation. Context shared
  for challenge is disclosed; builder conclusions cannot be assumed as premises.
  Principal review expressly needs the drafted account. Unknown credential isolation
  remains unknown. Same-model review is permitted with a shared-blind-spot limitation.
- The review map is consumed by the set checker. If integrated into a gate, missing
  review/evidence transport fails closed; no ignored mandatory configuration key.
  CLI-supplied facts stay labelled supplied/unverified. The GitHub adapter cannot
  manufacture a review bundle from prose or equate a User account with a physical human.
- Gate result becomes metadata_conforming/failed. `verify_bundle.py` retains its
  separate byte-inventory `satisfied` result; `check_package.py` reports the combined
  `byte_integrity_verified` receipt. Update CLI and dashboard consumers together.
- Runtime dashboards distinguish candidate catalogue from the adopted version;
  counts are derived, not hardcoded. No My EA pin is rewritten.

## Concerns and containment

Privacy/data: only synthetic/review metadata in Git; no raw runtime/credential
evidence. Authority: read project/draft/official docs; write this branch and temp
test artifacts; ordinary feature push/PR permitted; no merge/release, identity or
account-permission mutation. Persisted data: no database migration. Dependencies:
isolated environment plus pinned validator requirements. Concurrency/lifecycle:
keep local dashboard operating; test in temporary stores and preserve unrelated work.
Resource bounds: records/artifacts and decoded bytes limited; no arbitrary resolver.
Platform/UI: no My EA/iOS flow change; existing Grafana catalogue views are affected.
Recovery: stop preview if needed, return to prior feature branch; pins unchanged.
Failure visibility: bounded validator errors, explicit unavailable/unknown status.
Scope uncertainty: no unresolved load-bearing design claim; independent final
implementation/runtime verification remains required before handoff.

## Independent design examination

`draft_schema_review` and `draft_policy_quality` identified schema/identity/evidence
and false-green defects; their initial turns ended before final clearance.
`evidence_principal` performed a bounded independent specialist/Quality design
examination and reproduced current evaluator defects. `draft_policy_quality`
subsequently completed separate adversarial design clearance with the corrected
decisions above. Neither design review certifies implementation or operations.
