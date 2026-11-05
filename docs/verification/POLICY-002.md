# POLICY-002 — Validation and independent review

Date: 5 November 2026. Candidate branch: `feature/review-records-agentic-policy`,
stacked on the open evidence/dashboard change. No merge, release, identity
provisioning or My EA adoption-pin update is implied by this record.

## Assessment of the supplied review and draft

The review's snapshot description is older than current repository state: main
already contains the merged baseline; the dashboard change is a separate open PR.
Its substantive evaluator findings remained reproducible, including path false
positives/negatives, self-acceptance without a report caveat, nonempty placeholders
appearing satisfied and ignored active dissent. The review schema and agentic
rules are the foundation, but those misleading-output fixes accompany them.

The attachment was a proposal, not an instruction to publish or bypass review.
It was not adopted verbatim. Changes include conditional-clearance rejection,
hash-bound supplied evidence, external subject/builder/account binding, honest
unavailable records, model-family consistency and explicit shared-account gaps.
Principal review may challenge a supplied account without treating its conclusions
as premises. Trusted human instructions remain part of the instruction hierarchy.

## Implementation and verification

- Original CODE-001–038 objects are preserved exactly. Their canonical JSON SHA256
  is `95ea3bcf92f76bd94ecb24371d506c074134e5337949866dbb3379f1f82eca45`.
- Candidate catalogue contains 50 rules. Coverage is **0 enforced, 5 partially
  detected, 45 guidance-only**. The two extra detectors concern record metadata
  and set completeness; they do not certify independent or human review.
- **89 tests passed on Python 3.12 and Python 3.9.6.** Both environments installed
  the same hash-locked dependencies. Tests include schema/format/duplicate keys,
  no arbitrary resolver, resource bounds, changed bytes/account, unknown policy,
  builder/session/subject mismatch, conditions, model contradictions, supersession,
  role/trigger coverage, missing dependency, actual CLI exit contracts, account
  self-acceptance/dissent, risk near misses and existing evidence/runtime regressions.
- Official jsonschema 4.25.1 package metadata declares Python >=3.9. A proven
  Draft202012Validator and explicit RFC3339 checker replace a custom schema engine.
- The synthetic complete review-set CLI returns `metadata_conforming` and explicit
  unauthenticated-origin/credential/semantic-review gaps. Synthetic examples are
  not actual reviews or acceptance evidence.
- The generated policy matches its maintained source. Two independently built
  23-file candidate bundles have identical manifests and verify exactly. CI now
  installs the hash lock, tests Python 3.9/3.12 and repeats the package checks.
  The first remote attempt failed before tests because ubuntu-latest selected
  Ubuntu 26.04 without a Python 3.9 build. The official actions/python-versions
  manifest lists Python 3.9.25 for Ubuntu 24.04; the runner is pinned to that
  supported image while keeping both versions and every test required.
  `verify_bundle.py` retains its inventory `satisfied` API; the aggregate package
  check reports `byte_integrity_verified`. Neither is a governance clearance.
- All real Grafana panel/filter queries passed. Builder used gstack login and
  inspected a screenshot showing candidate 1.1.0-rc.1 separately from adopted
  1.0.0-rc.1. API returned 50 candidate rows, with the 12 new requirements marked
  not in My EA's recorded adoption. Source health was fresh. Temporary synthetic
  dashboard fixtures were removed. No private snapshots/screenshots enter Git.
- My EA remains on its existing integration branch with only its two pre-existing
  untracked drafts; no app, local adapter or adoption pin was edited.

## Independent specialist review

`draft_schema_review` first identified weak evidence binding, conditional counting,
identity/model contradictions and shared-credential assumptions. Final implementation
review independently reran **50 focused tests**, all passing, plus direct mutations.
Hidden conditions, model-family contradictions, agent deferral of a high finding,
builder substitution and missing head-bound artifacts were all rejected.

Final verdict: ready within declared metadata-validation scope; no remaining
blocking finding. A documentation challenge was accepted: CODE-039's coverage
now describes acceptance-basis reporting as implemented, while identity enforcement
remains unmet. Core reviewed hashes:

```text
946b0ce3061167afe725e66e708bcff551f1551d4a9ddfe86a02e6a859a03695  tooling/review_records.py
78f877c0fe7be924866469f65197647de65152c41baddb0facd9031daeb7984e  policy/schemas/review-record.schema.json
```

## Independent adversarial/Quality review

`draft_policy_quality` separately cleared the corrected design and reviewed the
implementation. It independently reran **57 focused tests**, all passing, and
seven direct counterexamples. Conditions, wrong builder/session, missing head-bound
artifact, contradictory families, wrong principal account and non-clear supersession
were rejected; the unchanged complete synthetic control conformed.

Final verdict: ready within the reviewed implementation scope, no remaining
blocking finding. One wording challenge confused the aggregate package receipt
with the exact verifier API. Source/tests confirm they are separate; the spec
now names both explicitly rather than changing the verified API unnecessarily.
Reviewer core hashes additionally include:

```text
930db69fa455a6af926f241f510868468c5df6a9f546979186f44c0c2c150afa  tooling/check_gate.py
2fd3e85fd9733dd3e1cca5c54fd1af522e0ffd2df0fb8f9b60b30cefd63b3444  tooling/github_gate.py
```

A final CLI-transport regression was added after these independent executions;
it passes in the 89-test builder suites and does not change reviewed implementation bytes.

Both reviewers inspected code and ran bounded independent probes. The full
cross-version suite and browser/runtime executions are the builder's separate
evidence; they are not attributed to reviewer execution.

## Principal examination and remaining work

`evidence_principal` independently examined the design, reproduced evaluator
defects and reviewed substantive accounts. Valid challenges removed an unsupported
size claim and corrected phase language. It also verified preservation of the
original 38 rules. No contribution was invented for drafts with no new challenge.

Still outside this candidate: constrained separate agent credentials/identities,
authenticated review-origin transport, automatic PR-comment record ingestion,
signed tags/attestations and full core/profile extraction. The GitHub adapter
supports explicit operator-supplied local bundles and fails closed when required
review metadata is absent. Existing adopter pins stay unchanged until separately
updated; no new policy release is published here.
